# Testing Report

## Overall Approach

I used sample tests provided in addition to some manual tests using Postman to test my implementation.
I followed the suggested approach in project spec and divided the project into 3 parts.
Part 1 for implementing a simple MESSAGE QUEUE, part 2 for implementing ELECTION mechanism, and part 3 for LOG REPLICATION.
My testing process therefore is also divided into 3 parts.

## Custom Configuration for Test

Some tests on specific log replication scenarios require the system to be in specific states that is difficult to achieve with manual operations.

I have modified the way `node.py` parses `config.json` so that for each node, extra parameters such as starting roles and starting logs can be passed into `config.json`.
These extra parameters will force raft nodes to start in certain states, for example, starting in higher terms with list of log entries.
My `Node` class will parse these parameters (if they exist), and be initialized accordingly.

After starting the system in specific states, I observe that AppendEntries and RequestVotes RPCs will bring the system to the desired state for each test.

## Part 1: Testing Message Queue implementation

To test my MessageQueue implementation, I simply spun up a single server and used Postman to test all the endpoints as specified in 5.2 of project spec.

Most of the cases are already covered in sample test suites.

## Part 2: Testing Election

In part 2, I added election mechanism without looking at log replication or the state machine.

In this part, I am only testing the heartbeat mechanism, randomized election timer, and fault-tolerance of leader election mechanism.

Certain parts of the election process is tied to log replication (candidate with outdated log will not be elected for safety), but this is tested in Part 3 later when I implement log replication.

For this part, I conducted the following tests manually:

1. One and only one leader is elected in a cluster

- To test this, I simply spun up a 5 servers cluster and used debug logs to check that a leader has been elected and is sending heart beats (AppendEntries RPC) with empty entries to all other servers

2. When leader crashes, a new leader is elected. The leader election algorithm is fault tolerant up to N/2 - 1 nodes crashing

- Following from the previous test, I tested the fault-tolerance of the election mechanism by reducing the number of active servers from 5 to 3 one by one. I kill the leader of the 5-servers cluster, and confirm that a new leader is elected in the 4-servers cluster, and repeat this process to confirm that a leader is elected in a 3-servers cluster as well.
- Since Raft is not fault-tolerant when majority of servers are down, I do not test how the system behaves when only 2 or less server is up. The election cycles will continue indefinitely without ever electing a leader, since no one can garner majority votes.

3. Leadership election is not affected by a node crashing and recovering (partition)

- This test case follows from the previous test. After crashing few servers, I start them back up and confirm that they get heart beats from the leader and get re-integrated into the cluster

4. The `GET /status` endpoint is working correctly

- I test the `GET /status` endpoints by querying each of the server in the cluster, and make sure that the leader server returns 'Leader' and others return 'Follower'.
- To test whether the endpoint correctly returns candidate status is bit difficult manually since elections end in matter of seconds, so I deliberately kill more than half of the servers and force a server to run elections indefinitely and checked that 'Candidate' status is returned by the API.

5. Test that if election time outs while a candidate, new election is started

- I simply spin up 1 server in a 5 servers cluster, and confirm the single server will keep trying to hold elections as it waits for votes that are never coming

6. Test that if candidate receives AppendEntries RPC from new leader (higher or equal term), it converts to follower immediately and updates its term

- To run this test, I ran nodes using the config file `test/election_test_configs/force_candidate_step_down.json`
- I set up a node that is in candidate state trying to get votes, and another node that's already a leader with higher term sending AppendEntries to the node
- Slowing down election timer and heart beats timer make the debug entries easier to read, but one should see in candidate node's log that it has held an election for which it was forced to step down

## Part 3: Testing Log Replication

In part 3, I test for log replication.
To test certain specific scenarios, I had to force the system to start in particular states (for example, few nodes will have existing logs at start up with term > 0) and observe that they behave as expected.

To make testing in this part easier, I added an endpoint in Flask (`GET /force-view-state-machine`), which bypasses all restrictions and allow client to see the state of state-machine whether the server is a Leader or not.

### Tests for Basic Log Replication Logic

1. Test that log entry will not be commited when less than half of the majority of number of servers are present

- I simply spin up a single server in a cluster and check that client requests never get a reply because the leader can never get enough acknowledgements from followers that log has been replicated to majority.

2. Test that logs are replicated across the cluster

- I spin up 5 servers in a cluster, check the leader based on who is sending AppendEntries in the logs, and then send multiple requests
- Then I use `GET /force-view-state-machine` to check that states has been replicated on all servers in the cluster

3. Test for fault-tolerance

- I simply shut down servers till there are only 3 servers left in a 5 servers cluster, and observe that all states are still retained
- I also test that the new leader can still commit new logs and replicate it across the cluster's remaining nodes

### Tests for Specific Log Replication States

4. Follower has missing entries present on the leader

- To test this, need to start the program using `test/log_replication_tests/follower_missing_entries.json`
- The config file will start a cluster in which the leader node has multiple uncommited logs that the follower is missing
- After spinning up the cluster, I wait a bit (for AppendEntries to complete), and observe that state has been successfully replicate across the leader and the follower

5. Follower has extra uncommitted entries that's not on the leader
6. New leader successfully commits uncommited entry from previous term in its own log (Paper section 5.4.2)

- I test the above two scenarios together using `test/log_replication_tests/follower_extra_entries.json`
- The test starts the cluster in a state similar to Figure 7 Case (d) in Raft paper. The leader will be in term 6, and the follower has many uncommited logs from term 5 that's not in the leader.
- I observe that after starting the cluster, initially no entries are being commited on both the leader and follower node. This is because the leader starts in term 6, and it has no log entries in term 6. Following the safety rule laid out in 5.4.2 of the paper, leader only commit entries by counting replicas in its own term, so unless new log entries are being added, the leader will not advance its `commitIndex`.
- To start any committing process, I submit a random client request so that there are now new log entries in the term 6
- I observe that the extra entries in the follower from term 5 will be deleted, and the new client request log from term 6 will be replicated across leader and the follower
- FInally, I observe that all logs will be correctly applied to the state machine and client request answered

7. Follower has both missing and extra entries in relation to the leader

- The config file for this test is `test/log_replication_tests/missing_and_extra_entries.json`
- The logs mimic the state in Figure 7 case (f).
- I simply start the cluster and observe that both the leader and follower reach the correct state. The leader will force the follower to delete uncommited entries from previous terms that are inconsistent with the leader's log.

8. Test that AppendEntries is idempotent so receiving stale RPCs from the same term is ok

- The config file for this test is `test/log_replication_tests/append_entries_idempotent.json`
- I have a leader that will be trying to replicate entries that already exist in the log
- After several rounds of AppendEntries, check that no one has got any extra logs
  - This can be checked by letting the follower become the leader instead somehow, and check its log indices through console logs

9. Test that if candidate's log is not up-to-date as receiver's log, then no vote is granted and such candidate cannot be elected

- The config file for this test is `stale_candidate_get_no_vote.json`
- I simply have a node with very high terms but no log, and another node with very low term but lots of logs
- I check that the latter will reject the former's vote request

## Shortcomings of testing approach

Since most of my tests are done manually (with some aids from the config file), they might not be the most comprehensive.

While I have taken into account concurrency issues by using locks on critical sections, I may have missed few race conditions that can be detected only by algorithmically varying test conditions and timing on specific situations. These things are very hard to detect with manual testing, as sometimes subtle race conditions do not lead to inconsistent state and so are left undetected.

Another shortcoming of manual testing is that I have not tested what will happen to the system when there are loads of client requests, so I am not sure how performant my implementation of Raft is under stress.

Finally, there are still many other specific situations that Raft algorithm could fall into that I have not tested on. It is time consuming to set up the appropriate config file to make sure that all situations are covered, so a programmed framework (such as the JavaScript visualization on Raft website) would have allowed for more comprehensive testing.
