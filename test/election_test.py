from test_utils import Swarm, Node, LEADER, FOLLOWER, CANDIDATE
import pytest
import time
import requests

# seconds the program will wait after starting a node for election to happen
# it is set conservatively, you will likely be able to lower it for faster tessting
ELECTION_TIMEOUT = 0.3

# array of numbr of nodes spawned on tests, an example could be [3,5,7,11,...]
# default is only 5 for faster tests
NUM_NODES_ARRAY = [5]


# yoour `node.py` file path
PROGRAM_FILE_PATH = "../src/node.py"


@pytest.fixture
def swarm(num_nodes):
    swarm = Swarm(PROGRAM_FILE_PATH, num_nodes)
    swarm.start(ELECTION_TIMEOUT)
    yield swarm
    swarm.clean()


def collect_leaders_in_buckets(leader_each_terms: dict, new_statuses: list):
    for i, status in new_statuses.items():
        assert ("term" in status.keys())
        term = status["term"]
        assert ("role" in status.keys())
        role = status["role"]
        if role == LEADER:
            leader_each_terms[term] = leader_each_terms.get(term, set())
            leader_each_terms[term].add(i)


def assert_leader_uniqueness_each_term(leader_each_terms):
    for leader_set in leader_each_terms.values():
        assert (len(leader_set) <= 1)


@pytest.mark.parametrize('num_nodes', [1])
def test_correct_status_message(swarm: Swarm, num_nodes: int):
    status = swarm[0].get_status().json()
    assert ("role" in status.keys())
    assert ("term" in status.keys())
    assert (type(status["role"]) == str)
    assert (type(status["term"]) == int)


@pytest.mark.parametrize('num_nodes', [1])
def test_leader_in_single_node_swarm(swarm: Swarm, num_nodes: int):
    status = swarm[0].get_status().json()
    assert (status["role"] == LEADER)


@pytest.mark.parametrize('num_nodes', [1])
def test_leader_in_single_node_swarm_restart(swarm: Swarm, num_nodes: int):
    status = swarm[0].get_status().json()
    assert (status["role"] == LEADER)
    swarm[0].restart()
    time.sleep(ELECTION_TIMEOUT)
    status = swarm[0].get_status().json()
    assert (status["role"] == LEADER)


@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_is_leader_elected(swarm: Swarm, num_nodes: int):
    leader = swarm.get_leader_loop(3)
    assert (leader != None)


@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_is_leader_elected_unique(swarm: Swarm, num_nodes: int):
    leader_each_terms = {}
    statuses = swarm.get_status()
    collect_leaders_in_buckets(leader_each_terms, statuses)

    assert_leader_uniqueness_each_term(leader_each_terms)


@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_is_newleader_elected(swarm: Swarm, num_nodes: int):
    leader1 = swarm.get_leader_loop(3)
    assert (leader1 != None)
    leader1.clean(ELECTION_TIMEOUT)
    leader2 = swarm.get_leader_loop(3)
    assert (leader2 != None)
    assert (leader2 != leader1)
