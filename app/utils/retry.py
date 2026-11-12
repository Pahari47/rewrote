import random

BASE_DELAY = 2
MAX_DELAY = 60

def calaculate_retry_delay(attempt: int) -> float:
    exponential_delay = min(MAX_DELAY, BASE_DELAY * (2 ** (attempt - 1)))

    return random.uniform(0, exponential_delay)