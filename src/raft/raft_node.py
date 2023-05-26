from enum import Enum
import threading
import requests
import time

from raft.logg import debug_print, error_print
from raft.custom_timer import ResettableTimer
from raft.ballot_box import BallotBox
from raft.protocol import *
from message_queue.state_machine import StateMachine

class Role(Enum):
    Follower = "Follower"
    Leader = "Leader"
    Candidate = "Candidate"
    
class Node:
    def __init__(self, id, peers, test_params={}):
        
        # Basic config for nodes
        self.id = id
        if 'role' in test_params: 
            if test_params['role'] == 'leader':
                self.role = Role.Leader # Set leader explicitly for testing purposes
            elif test_params['role'] == 'candidate':
                self.role = Role.Candidate # Set node to start as candidate explicity for testing purposes
        else:
            self.role = Role.Follower # Every node starts as a follower
        self.peers = peers
        
        # Persistent state on all servers
        self.log: list[LogEntry] = []
        if 'log' in test_params:
            self.log : list[LogEntry] = test_params['log'] # Set default logs for testing purpose
        
        if 'term' in test_params:
            self.current_term = test_params['term']
        else:
            self.current_term = 0
        if 'voted_for' in test_params:
            self.voted_for = test_params['voted_for'] # candidateId that received vote in current term (or null if None)
        else:
            self.voted_for = None
        
        # Volatile state on all servers
        self.commit_index = 0 
        self.last_applied = 0
        
        # Volatile state on leaders, initialized to None because node starts as Follower
        self.leader_state_lock = threading.Lock() # Need a lock to manage concurrent updates by multiple AppendEntries responses to the leader
        if 'next_index' in test_params:
            self.next_index = test_params['next_index'] # For testing purpose
        else:
            self.next_index = None
        if 'match_index' in test_params:
            self.match_index = test_params['match_index'] # For testing purpose
        else:
            self.match_index = None
        
        # State machine related
        self.quorum = 1 if len(self.peers) == 0 else (len(self.peers) + 1) // 2 + 1 # Must be >= quorum for consensus
        self.state_machine = StateMachine()
        self.lock = threading.RLock() # Lock for updating role, current_term, and voted_for; using re-entrant lock because certain function acquires the lock twice in a thread
        
        # Daemon process in node (election, heartbeat, updating commit index)
        self.election_timer = ResettableTimer(self.run_election, 250, 300) # Default 250 ~ 300ms timeouts
        self.heartbeat_timer = ResettableTimer(self.append_entries, 25, 35) # Recommended 25 ~ 35
        if 'role' in test_params and test_params['role'] == 'leader':
            self.heartbeat_timer.run() # Explicitly set the node as leader by starting heart beat from the onset
        else: 
            self.election_timer.run() # Starts a election timer at start up in the usual case
        threading.Thread(target=self.advance_commit_and_apply_daemon, daemon=True).start() # Start advance commit daemon
        
        
    """
    Interface for interacting with the web server (rpc handler, client request handler)
    """
        
    def rpc_handler(self, sender_id:int, rpc_message_json:dict):
        '''
        Parse rpc request and handle accordingly
        '''
        debug_print("received rpc str", sender_id, rpc_message_json)
        rpc_message = deserialize(rpc_message_json)
        debug_print("received rpc", rpc_message)
        
        if rpc_message_json['class'] == 'VoteRequestMessage':
            res, code = self.handle_vote_request(rpc_message, sender_id)
            debug_print('responded to rpc: {} with code {}'.format(res, code))
            return res, code
        elif rpc_message_json['class'] == 'AppendEntriesMessage':
            res, code = self.handle_append_entries(rpc_message, sender_id)
            debug_print('responded to rpc:{} with code {}'.format(res, code))
            return res, code
    
    
    def respond_to_client_append_entries(self, command: Command):
        '''
        Respond to client requests to Flask app
        '''
        # Step 0:        
        if self.role != Role.Leader:
            return ClientResponse(False, {})
        
        # Step 1: Append command locally without committing, attach Event to it
        # Also build up RPC input
        with self.lock:
            log_entry_idx = len(self.log) + 1 
            log_entry = LogEntry(self.current_term, log_entry_idx, command, '')
            self.log.append(log_entry) # Append to local log 
            
        # Step 2: Wait for state machine to apply the command
        # Return response to client that command successfully applied
        while self.last_applied < log_entry_idx or self.role != Role.Leader:
            time.sleep(1e-6)
        if self.role == Role.Leader:
            return ClientResponse(True, log_entry.result)
        else:
            # Server no longer a leader while trying to replicate log
            return ClientResponse(False, {})
    
    def respond_to_client_get_status(self):
        with self.lock:
            # Role and term must be atomically returned
            return self.role.name, self.current_term
    
    def debug_show_state_machine_state(self):
        '''
        For observability during debugging and testing only
        '''
        return self.state_machine.message_queue._print_queue_state()
    
    '''
    Log replication functions
    append_entries (heartbeat daemon)
    send_append_entry (to a single server)
    handle_append_entries
    advance_commit_and_apply (move state machine forward)
    '''
    
    def append_entries(self):
        '''
        A daemon process managed by timer, send AppendEntries to all peers periodically
        '''
        if self.role == Role.Leader: 
            for peer_idx, peer in enumerate(self.peers):
                port = peer[1]
                # Step 1: Check if there is any entry to append
                next_index = self.next_index[peer_idx]
                if len(self.log) >= next_index:
                    # Got entries to send
                    prev_log_index = next_index - 1
                    entries = self.log[next_index - 1 : len(self.log)]
                else:
                    # Send heartbeat
                    prev_log_index = len(self.log)
                    entries = []
                # Common info to include for both heartbeats and regular append
                prev_log_term = 0
                if prev_log_index > 0:
                    #debug_print("Prev log term is {}".format(prev_log_term))
                    prev_log_term = self.log[prev_log_index - 1].term
                append_entry_msg = AppendEntriesMessage(self.current_term, self.id, prev_log_index, prev_log_term, entries, self.commit_index)
                
                # Step 2: Send RPC on separate thread
                thread = threading.Thread(target=self.send_append_entry, args=(append_entry_msg, peer_idx, port), daemon=True)
                thread.start()     
            self.heartbeat_timer.reset()
        else:
            error_print('No longer the leader, cancel heartbeats')
            self.heartbeat_timer.cancel() # Cancel the heartbeats till server becomes a leader again
            
                
    def send_append_entry(self, msg:AppendEntriesMessage, peer_idx:int, port:int):
        '''
        Send AppendEntries RPC to one peer
        '''
        url = f"http://localhost:{port}/rpc/{self.id}"
        json_paylod = serialize(msg)
        try:
            debug_print('Sent AppendEntries to port {} with entries {}'.format(port, msg.entries))
            response = requests.post(url, json=json_paylod)
            if response and response.ok:
                debug_print("received AppendEntriesResponse from {}".format(port))
                response_body = response.json()
                if not response_body['success']:
                    if response_body['term'] > self.current_term:
                        self.update_term(response_body['term'])
                    else:
                        debug_print("AppendEntries failed for {}, has to reduce next index by 1".format(port))
                        with self.leader_state_lock:
                            self.next_index[peer_idx] = max(1, self.next_index[peer_idx] - 1)
                else:
                    if response_body['term'] < self.current_term:
                        # Edge case of stale response when there is a new term (and potentially new leader!)
                        debug_print("Received stale response, ignore!")
                    else:
                        mmatch_idx = response_body['matchIndex']
                        # Stale response as in the entries sent have already been appended (potential duplicate RPCs)
                        with self.leader_state_lock:
                            stale_response = self.next_index[peer_idx] > len(self.log) or mmatch_idx <= self.match_index[peer_idx]
                            if not stale_response:
                                self.match_index[peer_idx] = mmatch_idx
                                self.next_index[peer_idx] = self.match_index[peer_idx] + 1
                        debug_print("AppendEntries response was successful, the new match index for port {} is {}".format(port, mmatch_idx))
            # If response not ok, then ignore response and let heartbeat daemon send the retry
        except Exception as e:
            error_print(str(e))
            
            
    def handle_append_entries(self, message:AppendEntriesMessage, sender_id:int):
        '''
        Handle AppendEntries RPC message
        '''
        # Step 1: If term < currentTerm, reply False immediately
        try:
            debug_print('Processing AppendEntriesMessage : {}'.format(message))
            current_term = self.current_term
            if message.term < current_term:
                debug_print("Received expired message from last term: {} from {}, current term is {}".format(message.term, message.leaderId, current_term))
                return {'success': False, 'term': current_term}, 200
            else:
                # This is a valid heartbeat, so reset election timer
                # If Candidate, then AppendEntries from same term also counts
                if current_term < message.term or (self.role == Role.Candidate and current_term == message.term):
                    # New leader has emerged! 
                    self.update_term(message.term)
                self.election_timer.reset() # Any valid AppendEntries RPC act as a heartbeat

            
            # Step 3: Reply false if log doesn't contain an entry at prevLogIndex whose term
            # matches prevLogTerm
            prev_log_index = message.prevLogIndex
            prev_log_term = message.prevLogTerm
            if prev_log_index > 0 and prev_log_term > 0:
                if len(self.log) < prev_log_index or self.log[prev_log_index - 1].term != prev_log_term:
                    debug_print("Log doesn't contain an entry at prevLogIndex ({}) whose term matches prevLogTerm ({})".format(prev_log_index, prev_log_term))
                    return {'success': False, 'term': current_term}, 200
            
            # Step 4 + 5: If an existing entry conflicts with a new one (same index but diff terms)
            # delete the existing entry and all that follow it; 
            # Append any new entries not already in the log
            with self.lock:
                # Need to lock to prevent interleaved update of logs
                entries = message.entries                
                for entry in entries:
                    entry_idx = entry['index']
                    if len(self.log) >= entry_idx:
                        if self.log[entry_idx - 1].term != entry['term']:
                            self.log = self.log[0:entry_idx - 1] # cutting entry such that log[entry_idx - 1:len(log)] is gone
                            debug_print("Containing conflicting entry at index {}, deleting these entries after this index!".format(entry_idx))
                        elif self.log[entry_idx-1].term == entry['term']:
                            # By the log matching property, this log must have already been appended
                            continue
                    # Now we can append entries safely
                    command_to_append = globals()["Command"](**entry['command'])
                    log_entry_to_append = LogEntry(entry['term'], entry['index'], command_to_append, '')
                    self.log.append(log_entry_to_append)
            
                # Step 6: If leaderCommit > commitIndex, set commitIndex = min(leaderCommit, index of last new entry)
                if message.leaderCommit > self.commit_index:
                    debug_print("Advancing commit index from {} to {}".format(self.commit_index, message.leaderCommit))
                    self.commit_index = min(message.leaderCommit, len(self.log))
            
            # Step 7: Return RPC
            return {'success': True, 'term': current_term, 'matchIndex': message.prevLogIndex + len(message.entries)}, 200
        except Exception as e:
            error_print(str(e))
            return {'error': str(e)}, 500
        
        

    def advance_commit_and_apply_daemon(self):
        '''
        Daemon process managing commit index and state machine
        '''
        # Will continue operating regardless of role of the server
        while True:
            # Step 1: Go through match indexes and find if commit index should be advanced
            # Find an N such that N >= commit_index, a majority of match_index >= N, and log[N].term == current_term
           
            if self.role == Role.Leader:
                # Only leader can advance commit by checking match index
                # Follower must get append entries from leader
                if len(self.peers) != 0:
                    # Sort commit index 
                    sorted_match_idx = sorted(self.match_index)
                    median_idx = len(self.peers) // 2
                    median = sorted_match_idx[median_idx]
                    # Median is N candidate
                    if median > 0 and median > self.commit_index and self.log[median - 1].term == self.current_term:
                            debug_print("Advanced commit index to {}".format(median))
                            self.commit_index = median
                else:
                    # Single server swarm, so just advance commit directly
                    self.commit_index = len(self.log)
            
            # Step 2: Check last_applied
            # Leader and follower both advance state machine by checking last_applied vs. commit_index
            while self.commit_index > self.last_applied:
                self.state_machine.apply_log(self.log[self.last_applied])
                self.last_applied += 1
                debug_print("Advanced last_applied to {}".format(self.last_applied))

            # Step 3: Sleep for milisecs
            time.sleep(1e-6)        
            
    '''
    Election related functions
    '''

    def run_election(self):
        
        '''
        Daemon process managed by election timer
        '''
        
        if self.role == Role.Leader:
            # If election triggered due to timer when you are already a leader, do not do anything other than resetting the timer
            self.election_timer.reset()
            return
        
        with self.lock:
            self.role = Role.Candidate
            self.current_term = self.current_term + 1
            self.voted_for = self.id # vote for self
            self.election_timer.reset() # reset the timer. If election timeout elapses, start new election
            last_log_idx = len(self.log) 
            last_log_term = 0 if last_log_idx == 0 else self.log[last_log_idx - 1].term
            message = serialize(VoteRequestMessage(self.current_term, self.id, last_log_idx, last_log_term))
        
        debug_print("starting election by id-{}".format(self.id))
        
        majority_reached = threading.Event()
        ballot_box = BallotBox(self.id, majority_reached, self.quorum)
        for _ip, port in self.peers:
            thread = threading.Thread(target=self.send_request_vote, args=(port, message, ballot_box), daemon=True)
            thread.start()
        
        # Edge case when there is only one node in swarm:
        if len(self.peers) == 0:
            majority_reached.set()
            
        # Wait for election to complete
        while self.role == Role.Candidate and not majority_reached.is_set():
            # Wait till majority vote gained, or some other leader knocks the server out of Cnadidate state
            time.sleep(1e-6)

        if self.role == Role.Candidate and majority_reached.is_set():
            debug_print("{} won the election for term {}".format(self.id, self.current_term))
            # Start initializing states for leaders
            self.role = Role.Leader
            self.next_index = [len(self.log) + 1] * len(self.peers)
            self.match_index = [0] * len(self.peers)
            self.append_entries() # Start sending heartbeats RPCs
            #self.heartbeat_timer.reset() # Start sending heartbeat RPCs
            
        if self.role == Role.Follower:
            debug_print("Candidate converted to follower during election!")
        
    def send_request_vote(self, port:int, json_payload:dict, ballot_box: BallotBox):
        '''
        Send RequestVote RPC and process the response for one peer
        '''
        # Start a web request
        # If result is returned, modify the ballot box accordingly
        # If vote number reaches certain number, trigger event 
        try:
            response = requests.post(f"http://localhost:{port}/rpc/{self.id}", json=json_payload)
            if response and response.ok:
                data = response.json()
                debug_print("Received vote request response: {}".format(data))
                if data['term'] < self.current_term:
                    return # Ignore stale response and return (election probably ended anyway)
                if data['voteGranted']:
                    ballot_box.add_vote()
                elif self.current_term < data['term']:
                    # If vote note granted, do nothing unless term must be updated and hence candidate must step down
                    self.update_term(data['term'])
        except Exception as e:
            error_print('request for vote from {} to {} timed out! - {}'.format(self.id, port, str(e)))
        # If response is not ok, then request for vote has failed, don't do anything till another election is triggered
    
    def handle_vote_request(self, message:VoteRequestMessage, sender_id:int):
        '''
        Handle RequestVote RPC message
        '''
        try:
            with self.lock:
                # Need to lock to prevent duplicate votes 
                # i.e. vote for more than one candidate in a term by overwriting votedFor field
                if message.term < self.current_term:
                    # Reply false if term < currentTerm 
                    return {'term': self.current_term, 'voteGranted': False}
                elif message.term > self.current_term:
                    self.update_term(message.term)
                
                # Check if candidate's log is at least as up-to-date as receiver's log as defined in $5.2, $5.4
                # First compare the index and term of the last entries in the logs
                # If terms are the same, then compare log length
                candidate_stale = False
                last_term = 0 if len(self.log) == 0 else self.log[-1].term
                if last_term > message.lastLogTerm:
                    candidate_stale = True
                elif last_term == message.lastLogTerm and len(self.log) > message.lastLogIndex:
                    candidate_stale = True
                    
                # Check if the server has already voted for others in this term
                if (self.voted_for is None or self.voted_for == message.candidateId) and not candidate_stale:
                    self.role = Role.Follower
                    self.voted_for = message.candidateId
                    self.current_term = message.term
                    debug_print("Granting vote to: {}".format(message.candidateId))
                    return {'term': self.current_term, 'voteGranted': True}, 200
                else:
                    return {'term': self.current_term, 'voteGranted': False}, 200
        except Exception as e:
            return {'error': str(e)}, 500
        
    '''
    Util functions
    '''
    
    def get_last_log_term(self):
        if len(self.log) == 0:
            return 0
        else:
            return self.log[-1].term
    
    def update_term(self, new_term:int):
        '''
        For node to step down as leader or candidate when receiving RPC of higher term
        '''
        with self.lock:
            self.role = Role.Follower
            self.current_term = new_term
            self.voted_for = None 
            self.heartbeat_timer.cancel() # Stop sending heartbeats if server was a leader
        debug_print('{} stepped down as Leader and entered term {} as Follower'.format(self.id, new_term))