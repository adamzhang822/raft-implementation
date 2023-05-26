from flask import Flask, request,jsonify, Response
import json
import raft.raft_node as Node
from raft.protocol import Command, ClientResponse

raft_node : Node = None

app = Flask(__name__)

@app.route('/topic', methods=['GET', 'PUT'])
def topic():
    
    if request.method == 'PUT':
        # Get request content
        data = request.json
        topic = data['topic']
        command = Command('topic', 'PUT', {'topic':topic})
        res:ClientResponse = raft_node.respond_to_client_append_entries(command)
        if res.responded and res.body['success']:
            return jsonify(success=True), 201
        else:
            return jsonify(success=False), 400
        
    if request.method == 'GET':
        # Do not need to commit read request to state machines
        command = Command('topic', 'GET', '')
        res:ClientResponse = raft_node.respond_to_client_append_entries(command)
        if res.responded and res.body['success']:
            return Response(json.dumps({'success':True, 'topics':res.body['topics']}, indent=4), status=200, mimetype='application/json')
        else:
            return jsonify(success=False), 400
    
@app.route('/message', methods=['PUT'])
def put_message():
    
    data = request.json
    topic = data['topic']
    message = data['message']
    command = Command('message', 'PUT', {'topic': topic, 'message': message})
    res:ClientResponse = raft_node.respond_to_client_append_entries(command)
    
    if res.responded and res.body['success']:
        return jsonify(success=True), 201
    else:
        return jsonify(success=False), 400


@app.route('/message/<path:topic>', methods=['GET'])
def get_messages(topic):
    
    command = Command('message', 'GET', {'topic':topic})
    res = raft_node.respond_to_client_append_entries(command)
    if res.responded and res.body['success']:
        return jsonify(success=True, message=res.body['message']), 200
    else:
        return jsonify(success=False), 400
    
@app.route('/status', methods=['GET'])
def get_status():
    role, term = raft_node.respond_to_client_get_status()
    return jsonify(role=role, term=term), 200

@app.route("/rpc/<id>", methods=["POST"])
def handle_rpc(id):
    rpc_message_json = request.json
    res, code = raft_node.rpc_handler(id, rpc_message_json)
    response = Response(json.dumps(res, indent=4), status=code, mimetype='application/json')
    return response

@app.route("/force-view-state-machine", methods=["GET"])
def force_view_state_machine():
    '''
    For debugging, will return the state of the message queue in the server forcefully (even if you are querying a non-leader)
    '''
    state_machine_view = raft_node.debug_show_state_machine_state()
    return state_machine_view, 200