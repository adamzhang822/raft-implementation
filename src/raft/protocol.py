import dataclasses
from dataclasses import dataclass
from threading import Event

@dataclass 
class Command:
    endpoint: str
    method: str
    body: str

@dataclass
class LogEntry:
    term: int
    index: int
    command: Command
    result: str

@dataclass
class VoteRequestMessage:
    term: int
    candidateId: int
    lastLogIndex: int
    lastLogTerm: int
    
@dataclass
class VoteRequestResponse:
    term: int 
    voteGranted: bool
    
@dataclass
class AppendEntriesMessage:
    term: int
    leaderId: int
    prevLogIndex: int
    prevLogTerm: int
    entries: list[LogEntry]
    leaderCommit: int
    
@dataclass
class AppendEntriesResponse:
    term: int
    success: bool
    
@dataclass
class ClientResponse:
    responded: bool 
    body: dict
    
def serialize(rpc):
    return {"class": rpc.__class__.__qualname__, "dict": dataclasses.asdict(rpc)}

def deserialize(rpc_dict):
    return globals()[rpc_dict["class"]](**rpc_dict["dict"])



'''
command = Command('topic', 'PUT', {'topic':'dogs', 'message': 'i love dogs!'})
entry = LogEntry(1, 1, command, '')
command2 = Command('topic', 'PUT', {'topic':'cats'})
entry2 = LogEntry(1, 1, command2, '')

print(entry.command.body['topic'])

"""
append_message = AppendEntriesMessage(1, 0, 1, 1, [command, command2], 1)
append_json = serialize(append_message)
print(append_json['dict']['entries'][0]['body']['topic'])
"""
'''



