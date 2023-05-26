from collections import deque
import threading

class MessageQueue:
    
    def __init__(self):
        self.topics = {}
    
    def add_topic(self, topic):
        if topic in self.topics:
            # Check if by the time lock acquired, topic has already been added
            # by another thread
            return False
        self.topics[topic] = deque()
        return True
        
    def get_topics(self):
        # Ok to return stale list of topics
        return list(self.topics.keys())
    
    def put_message(self, topic, message):
        if topic not in self.topics:
            return False
        self.topics[topic].append(message)
        return True
    
    def get_message(self, topic):
        if topic not in self.topics:
            return False # topic not in queues 
        if not self.topics[topic]:
            return None # topic in queues, but empty
        return self.topics[topic].popleft()
    
    def _print_queue_state(self):
        '''
        For observability into system state while debugging and testing only
        '''
        res_str = ''
        for topic in self.topics:
            res_str += topic + ':{}'.format(str(self.topics[topic])) + '\n'
        return res_str