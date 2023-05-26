import json
import sys

import server
from server import app
from raft.raft_node import Node
from raft.protocol import *


def convert_to_log_list(log_list):
    res : list[LogEntry] = []
    for log in log_list:
        command : Command = globals()["Command"](**log['command'])
        entry : LogEntry = LogEntry(log['term'], log['index'], command, {})
        res.append(entry)
    return res

def parse_config_json(fp, idx):
    config_json = json.load(open(fp))

    my_ip, my_port = None, None
    peers = []
    for i, address in enumerate(config_json["addresses"]):
        ip, port = address["ip"], str(address["port"])
        if i == idx:
            my_ip, my_port = ip, port
        else:
            peers.append((ip, port))

    assert my_ip, my_port
    info = config_json["addresses"][idx]
    if 'log' in info:
        log_list = info['log']
        processed_log = convert_to_log_list(log_list)
        info['log'] = processed_log
    return my_ip, my_port, peers, info


if __name__ == "__main__":
    config_json_fp = sys.argv[1]
    config_json_idx = int(sys.argv[2])
    _my_ip, my_port, peers, info = parse_config_json(config_json_fp, config_json_idx)
    server.raft_node = Node(config_json_idx, peers, info)
    app.run(debug=False, host="localhost", port=my_port, threaded=True)