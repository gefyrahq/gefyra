import logging
import time

logger = logging.getLogger(__name__)


def stopwatch(func):
    def wrapper(*args, **kwargs):
        tic = time.perf_counter()
        result = func(*args, **kwargs)
        toc = time.perf_counter()
        logger.info(f"Operation time was {(toc - tic)*1000:0.4f}ms")
        return result

    return wrapper
