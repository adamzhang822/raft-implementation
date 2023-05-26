import logging
from threading import Lock

logging.basicConfig(
    format="%(levelname)s %(asctime)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S",
    # comment out to get it to log to the screen
    # filename="example.log",
    # overwrites - comment out to get append
    filemode="w",
    level=logging.DEBUG,
)

logger = logging.getLogger(__name__)

logger_lock = Lock()

def debug_print(*args):
    logger_lock.acquire()
    logger.debug(" ".join(len(args) * ["%s"]), *args)
    logger_lock.release()
    
def error_print(*args):
    logger_lock.acquire()
    logger.error(" ".join(len(args) * ["%s"]), *args)
    logger_lock.release()
