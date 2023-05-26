from test_utils import Swarm, Node, LEADER, FOLLOWER, CANDIDATE
import pytest
import time
import requests

NUM_NODES_ARRAY = [5]
PROGRAM_FILE_PATH = "../src/node.py"
TEST_TOPIC = "test_topic"
TEST_MESSAGE = "Test Message"

ELECTION_TIMEOUT = 0.3
NUMBER_OF_LOOP_FOR_SEARCHING_LEADER = 3


@pytest.fixture
def swarm(num_nodes):
    swarm = Swarm(PROGRAM_FILE_PATH, num_nodes)
    swarm.start(ELECTION_TIMEOUT)
    yield swarm
    swarm.clean()


def wait_for_commit(seconds=1):
    time.sleep(seconds)


@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_is_topic_shared(swarm: Swarm, num_nodes: int):
    leader1 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert (leader1 != None)
    assert (leader1.create_topic(TEST_TOPIC).json() == {"success": True})

    leader1.commit_clean(ELECTION_TIMEOUT)
    leader2 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert (leader2 != None)
    assert(leader2.get_topics().json() ==
           {"success": True, "topics": [TEST_TOPIC]})


@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_is_message_shared(swarm: Swarm, num_nodes: int):
    leader1 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert (leader1 != None)
    assert (leader1.create_topic(TEST_TOPIC).json() == {"success": True})
    assert (leader1.put_message(TEST_TOPIC, TEST_MESSAGE).json()
            == {"success": True})

    leader1.commit_clean(ELECTION_TIMEOUT)
    leader2 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert (leader2 != None)
    assert(leader2.get_message(TEST_TOPIC).json()
           == {"success": True, "message": TEST_MESSAGE})
