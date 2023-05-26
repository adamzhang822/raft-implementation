from subprocess import Popen, PIPE, signal
from json import dump

import time
import requests
import socket


MESSAGE = "/message"
TOPIC = "/topic"
STATUS = "/status"

FOLLOWER = "Follower"
LEADER = "Leader"
CANDIDATE = "Candidate"

CONFIG_PATH = "config.json"
IP = "127.0.0.1"
REQUEST_TIMEOUT = 1


class Node:
    def __init__(self,  program_file_path: str, config_path: str, i: int, config: dict, ):
        self.config = config
        self.i = i
        self.address = self.get_address()
        self.program_file_path = program_file_path
        self.config_path = config_path

    def start(self):
        self.startup_sequence = ["python3",
                                 self.program_file_path,
                                 self.config_path,
                                 str(self.i)]
        self.process = Popen(self.startup_sequence)
        self.wait_for_flask_startup()
        self.pid = self.process.pid

    def terminate(self):
        self.process.terminate()

    def kill(self):
        self.process.kill()

    def wait(self):
        self.process.wait(5)

    def pause(self):
        self.process.send_signal(signal.SIGSTOP)

    def resume(self):
        self.process.send_signal(signal.SIGCONT)

    def commit_clean(self, sleep=0):
        time.sleep(sleep)
        self.clean(sleep)

    def clean(self, sleep=1e-3):
        self.terminate()
        self.wait()
        self.kill()
        time.sleep(sleep)

    def restart(self):
        self.clean()
        self.start()

    def wait_for_flask_startup(self):
        number_of_tries = 20
        for _ in range(number_of_tries):
            try:
                return requests.get(self.address)
            except requests.exceptions.ConnectionError:
                time.sleep(0.1)
        raise Exception('Cannot connect to server')

    def get_address(self):
        address = self.config["addresses"][self.i]
        return "http://" + address["ip"]+":"+str(address["port"])

    def put_message(self, topic: str, message: str):
        data = {"topic": topic, "message": message}
        return requests.put(self.address + MESSAGE, json=data,  timeout=REQUEST_TIMEOUT)

    def get_message(self, topic: str):
        return requests.get(self.address + MESSAGE + '/' + topic,  timeout=REQUEST_TIMEOUT)

    def create_topic(self, topic: str):
        data = {"topic": topic}
        return requests.put(self.address + TOPIC, json=data, timeout=REQUEST_TIMEOUT)

    def get_topics(self):
        return requests.get(self.address + TOPIC, timeout=REQUEST_TIMEOUT)

    def get_status(self):
        return requests.get(self.address + STATUS, timeout=REQUEST_TIMEOUT)


class Swarm:
    def __init__(self, program_file_path: str, num_nodes: int):
        self.num_nodes = num_nodes

        # create the config
        config = self.make_config()
        dump(config, open(CONFIG_PATH, 'w'))

        self.nodes = [Node(program_file_path, CONFIG_PATH, i, config)
                      for i in range(self.num_nodes)]

    def start(self, sleep=0):
        for node in self.nodes:
            node.start()
        time.sleep(sleep)

    def terminate(self):
        for node in self.nodes:
            node.terminate()

    def clean(self, sleep=0):
        for node in self.nodes:
            node.clean()
        time.sleep(sleep)

    def restart(self, sleep=0):
        for node in self.nodes:
            node.clean()
            node.start()
        time.sleep(sleep)

    def make_config(self):
        return {"addresses": [{"ip": IP, "port": get_free_port(), "internal_port": get_free_port()} for i in range(self.num_nodes)]}

    def get_status(self):
        statuses = {}
        for node in self.nodes:
            try:
                response = node.get_status()
                if (response.ok):
                    statuses[node.i] = response.json()
            except requests.exceptions.ConnectionError:
                continue
        return statuses

    def get_leader(self):
        for node in self.nodes:
            try:
                response = node.get_status()
                if (response.ok and response.json()["role"] == LEADER):
                    return node
            except requests.exceptions.ConnectionError:
                continue
        time.sleep(0.5)
        return None

    def get_leader_loop(self, times: int):
        for _ in range(times):
            leader = self.get_leader()
            if leader:
                return leader
        return None

    def __getitem__(self, key):
        return self.nodes[key]


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    addr = s.getsockname()
    s.close()
    return addr[1]
