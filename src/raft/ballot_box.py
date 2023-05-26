import threading
from .logg import debug_print

class BallotBox:
    def __init__(self, id, event, threshold):
        self.id = id # for debugging purpose
        self.value = 1 # Every ballot box starts with a vote for itself!
        self._lock = threading.Lock()
        self._event = event
        self.threshold = threshold
        
    def add_vote(self):
        with self._lock:
            self.value = self.value + 1
            debug_print('vote granted to id {}'.format(self.id))
            if self.value >= self.threshold:
                self._event.set()