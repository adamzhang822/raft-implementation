from collections import deque
import threading
from .message_queue import MessageQueue
from raft.protocol import Command, LogEntry
import json

class StateMachine:
    
    def __init__(self):
        self.message_queue = MessageQueue()
        
    def apply_log(self, log_entry:LogEntry):
        '''
        Apply command to message queue
        '''
        
        # Step 1: Parse the log entry
        command:Command = log_entry.command
        endpoint = command.endpoint
        method = command.method
        body = command.body
        
        if endpoint == 'topic':
            if method == 'PUT':
                topic = body['topic']
                res = self.message_queue.add_topic(topic)
                log_entry.result = {'success': res}
            if method == 'GET':
                topics = self.message_queue.get_topics()
                log_entry.result = {'success': True, 'topics': topics}
        elif endpoint == 'message':
            if method == 'PUT':
                topic = body['topic']
                message = body['message']
                res = self.message_queue.put_message(topic, message)
                log_entry.result = {'success': res}
            if method == 'GET':
                topic = body['topic']
                res = self.message_queue.get_message(topic)
                if res is None or not res:
                    log_entry.result = {'success': False}
                else:
                    log_entry.result = {'success': True, 'message': res}
                    
    

    
    
    