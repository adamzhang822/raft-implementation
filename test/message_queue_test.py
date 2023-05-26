from test_utils import Swarm, Node

import pytest
import time
import requests

TEST_TOPIC = "test_topic"
TEST_MESSAGE = "Test Message"
PROGRAM_FILE_PATH = "../src/node.py"
ELECTION_TIMEOUT = 0.3


@pytest.fixture
def node_with_test_topic():
    node = Swarm(PROGRAM_FILE_PATH, 1)[0]
    node.start()
    time.sleep(ELECTION_TIMEOUT)
    assert(node.create_topic(TEST_TOPIC).json() == {"success": True})
    yield node
    node.clean()


@pytest.fixture
def node():
    node = Swarm(PROGRAM_FILE_PATH, 1)[0]
    node.start()
    time.sleep(ELECTION_TIMEOUT)
    yield node
    node.clean()


# TOPIC TESTS
def test_get_topic_empty(node):
    assert(node.get_topics().json() == {"success": True, "topics": []})


def test_create_topic(node):
    assert(node.create_topic(TEST_TOPIC).json() == {"success": True})


def test_create_different_topics(node):
    assert(node.create_topic(TEST_TOPIC).json() == {"success": True})
    assert(node.create_topic("test_topic_different").json()
           == {"success": True})


def test_create_same_topic(node):
    assert(node.create_topic(TEST_TOPIC).json() == {"success": True})
    assert(node.create_topic(TEST_TOPIC).json() == {"success": False})


def test_get_topic(node):
    assert(node.create_topic(TEST_TOPIC).json() == {"success": True})
    assert(node.get_topics().json() == {
           "success": True, "topics": [TEST_TOPIC]})


def test_get_same_topic(node):
    assert(node.create_topic(TEST_TOPIC).json() == {"success": True})
    assert(node.create_topic(TEST_TOPIC).json() == {"success": False})
    assert(node.get_topics().json() == {
           "success": True, "topics": [TEST_TOPIC]})


def test_get_multiple_topics(node):
    topics = []
    for i in range(5):
        topic = TEST_TOPIC + str(i)
        assert(node.create_topic(topic).json() == {"success": True})
        topics.append(topic)
    assert(node.get_topics().json() == {
           "success": True, "topics": topics})


def test_get_multiple_topics_with_duplicates(node):
    topics = []
    for i in range(5):
        topic = TEST_TOPIC + str(i)
        assert(node.create_topic(topic).json() == {"success": True})
        assert(node.create_topic(topic).json() == {"success": False})
        topics.append(topic)
    assert(node.get_topics().json() == {
           "success": True, "topics": topics})


# MESSAGE TEST


def test_get_message_from_inexistent_topic(node_with_test_topic):
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": False})


def test_get_message(node_with_test_topic):
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": False})


def test_put_message(node_with_test_topic):
    assert(node_with_test_topic.put_message(
        TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})


def test_put_and_get_message(node_with_test_topic):
    assert(node_with_test_topic.put_message(
        TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": True, "message": TEST_MESSAGE})


def test_put2_and_get1_message(node_with_test_topic):
    second_message = TEST_MESSAGE + "2"
    assert(node_with_test_topic.put_message(
        TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})
    assert(node_with_test_topic.put_message(
        TEST_TOPIC, second_message).json() == {"success": True})
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": True, "message": TEST_MESSAGE})


def test_put2_and_get2_message(node_with_test_topic):
    second_message = TEST_MESSAGE + "2"
    assert(node_with_test_topic.put_message(
        TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})
    assert(node_with_test_topic.put_message(
        TEST_TOPIC, second_message).json() == {"success": True})
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": True, "message": TEST_MESSAGE})
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": True, "message": second_message})


def test_put2_and_get3_message(node_with_test_topic):
    second_message = TEST_MESSAGE + "2"
    assert(node_with_test_topic.put_message(
        TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})
    assert(node_with_test_topic.put_message(
        TEST_TOPIC, second_message).json() == {"success": True})
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": True, "message": TEST_MESSAGE})
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": True, "message": second_message})
    assert(node_with_test_topic.get_message(
        TEST_TOPIC).json() == {"success": False})
