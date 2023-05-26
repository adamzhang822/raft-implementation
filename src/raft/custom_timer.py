import random
from threading import Timer

# https://stackoverflow.com/a/56169014
class ResettableTimer:
    def __init__(self, function, interval_lb=250, interval_ub=300):
        self.interval = (interval_lb, interval_ub)
        self.function = function
        self.timer = Timer(self._interval(), self.function)

    def _interval(self):
        return random.randint(*self.interval) / 1000

    def run(self):
        self.timer.start()

    def reset(self):
        self.timer.cancel()
        self.timer = Timer(self._interval(), self.function)
        self.timer.start()
        
    def cancel(self):
        self.timer.cancel()
