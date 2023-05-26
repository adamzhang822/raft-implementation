# Implementation

## Overall Implementation

### Communication Method

For communication between nodes, I used REST API. I simply added an endpoint on Flask App for RPC and implemented the RPCs as Post requests to that endpoint.

I used REST simply because the project specification did not place any requirements on communication methods, so I went with the one that has already been (partially) implemented in the sample implementation provided by Max.

REST is easy to implement as there are lots of flexibilities in deciding how and what to pass in messages as the request body. It is also easy for programmers as there is no low level complexity that need to be dealt with like socets programming.

The drawback to using REST is that there is a major security issue with the way I am using it. I am not distinguishing between the internal and external ports of server in my implementation since I simply have an extra API endpoint on the web server. Clients can directly invoke the RPC endpoints if they want. (However, requests to read or write on the message queue will only be handled by the Leader node). Since the project spec did not impose any security requirements, I ignored this issue.

Another drawback to using REST as opposed to ZMQ or RPC is that some functionalities of Raft is awkward to implement with REST. Since AppendEntries and VoteRequest are meant to be RPCs, using RPC mechanism could result in cleaner codes, whereas with REST you would have to implement several methods for specifically sending the RPC and processing the response.

With REST, certain messaging partterns are also dififcult to implement. For example, publish-subscribe pattern can be easily implemented with ZMQ, and it could be an appropriate messaging pattern for heartbeat mechanism, but it is difficult to do that with REST from scratch.

Finally, with REST, sending request and handling response are tied together so implementation pattern is limited. With ZMQ, handling incoming message and handling responses can be de-coupled as we can have separate queues to handle request type messages and response type messages.

### Communication Protocol

I defined common message types and command types (to state machine) in `protocol.py` to make type checking and autocomplete easier.

## Part 1: Message Queue

For message queue, there isn't much to discuss.
I am using a simple dictionary + Python deque to implement my MessageQueue class.
I am using deque over lists because deque offers faster append and pop which takes O(n) for lists.
Deque is not FIFO by default, so I enforce FIFO by only popping from first entry and appending after the last entry.

My message queue is not thread-safe as I do not use locks to protect critical sections. This is because my Raft implementation is such that a single thread will be handling updates to the state machine (as will be discussed in later sections), so there is no concerns of race conditions. My implementation ensures that log entries will be reflected on the state machine in a first-come-first-serve basis based on client request time.

Since our REST API does not involve deleting topics, and Python's `deque` is thread-safe for append and pop operations, not having thread safety is actually not a big concern.

If the API is also allowing for topic deletion and message editing, then more concurrency control is needed. For instance, we can use a Lock to lock modiciations to the object.

## Part 2: Leader Election

All of my leader election mechanism is implemented based on the TLA+ spec.

For election timer, I used `custom_timer.py` provided by Max in the starter project. After election is started, I use `Event` in Python's `threading` package to asynchronously manage the election. I have a class `BallotBox` which contains the `Event` object and a thread-safe counter that tallies votes each time a vote is received from RequestVote response. The `BallotBox` will set the `Event` object, which will notify the thread waiting on the `Event` object to be set to wake up. One possibility is that a Candidate is converted to a Follower before election is over, so aside from waiting for `Event` to be set, I also end the election process when the role of Candidate has changed.

Using `Event` makes it very easy to manage RequestVote RPC responses that's happening on other threads.

The VoteRequest RPC is done asynchronously by starting a daemon thread that makes a HTTP request. I am using Python's `requests` library. `requests` has default retry and timeout policies.

I did not change anything to define my retry and timeout policies. If RequestVote to certain node fails max_retries number of times (timeout or error code), the Candidate will never ask that server for vote again in the current election session. This is not a big issue, because if election times out, the candidate will simply restart another election, in which it will send another RequestVote to all servers.

For heartbeat, I simply re-use `custom_timer.py` and run the timer when a node is elected Leader. The timer will periodically invoke `append_entries` to send heartbeats (which is just empty entries for now).

## Part 3: Log Replication

I implemented log replication in two steps.

#### Step 1: Converting MessageQueue into StateMachine

First, I define a StateMachine class and inject MessageQueue as a dependency.
StateMachine class only has one method which is to apply actions on the message queue based on Command object supplied.
The Command object is defined in `protocols.py`, and the range of possible Commands are based on the REST endpoints defined in project spec which corresponds to the range of client requests on the message queue.

I re-wire everything so that client request will first be converted into a LogEntry object containing a Command object, and the LogEntry object is stored on Leader's log list without being applied to the StateMachine first.

Only until the log is being commited do I apply the log's command to the StateMachine which makes change on the MessageQueue accordingly, and only then does the Leader respond to the Client.

I keep track of when the Leader is ready to reply to the client by waiting on the node's `lastApplied` variable to meet the index corresponding to the client's request. How the `lastApplied` variable is moved is based on TLA+ spec, which I will explain more in the next section.

#### Step 2: Re-Implement AppendEntries so that it actually sends non-empty entries

I implemented `AppendEntries` with log replication as a daemon process in the Leader node that will be stopped when Leader steps down and restarted when re-elected.

The daemon process will send AppendEntries to all servers in a loop, and at the beginning of each loop, checks whether there are new entries to send to a particular server by checking the `nextIndex` value with respect to server's log lists. If there are no new entries to append, the RPC will turn into a simple heartbeat. Each AppendEntries request is sent asynchronously using thread.

I have decided to implement AppendEntries as a daemon process because it makes managing re-tries and heartbeats much easier. In Raft, Leader node will try AppendEntries indeiniftely until a response is gotten. Using a while loop that keeps sending unsent entries till `nextIndex` indicates otherwise naturally satisfies this constraint.

A potential drawback to this approach is that there is a small delay between when client request is submitted and the next round of AppendEntries is invoked. However, that delay is minimal if we set heartbeat rate to a smaller time interval. The benefit outweights the drawback, because it will be very difficult to manage AppendEntries retries if we do AppendEntries based on client requests, as we have to implement a separate daemon process for heartbeats when no requests are coming in.

#### Step 3: Implement AdvanceCommit

As suggested in the TLA+, I decoupled commitment process of logs and all AppendEntries into two daemon processed. The AdvanceCommit daemon will keep looking for new log entries that meet commitment criteria and advance the Leader node's commitIndex accordingly. Then, it will look at the StateMachine and if commitIndex has advanced ahead of state machine, the daemon process will also prompt state machines to execute the log entry.

When returning the result of executing a log to a client, there is a difficulty because there is a gap between when the server received client request and when it is fullfilled. Without some mechanism, the server will not know what the result was beyond that it was somehow executed on the state machine.

I considered several options. I considered using some sort of Futures obejct in Python's `concurrent.futures` library, but ended up just adding an extra field on LogEntry object that stores the result of execution for that particular log that can be directly returned to the client.

When `lastApplied` is incremented, the thread responding to client is notices it, and can then look for the execution result by looking up the corresponding LogEntry in log list.

I am trading space complexity for simplicity here, and one can also argue execution result is a useful thing to having in logs as well.

# Discussion

This implementation does not take into account configuration changes (adding new servers to the cluster midway), and does not implement any form of persistence of state machine and log data to stable storage. This implementation also does not implement any form of log compaction, so will not run correctly when log data grows indefinitely.

# Sources

- https://raft.github.io/
- https://realpython.com/intro-to-python-threading/#race-conditions
- https://docs.python.org/3/library/threading.html
- https://chelseatroy.com/?s=raft
- https://www.bogotobogo.com/python/Multithread/python_multithreading_Event_Objects_between_Threads.php
- https://www.reddit.com/r/flask/comments/qsentw/when_starting_a_thread_inside_a_flask_file_the/
