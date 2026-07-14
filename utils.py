import re
import time
from functools import wraps

def sanitize_filename(name):
    return re.sub(r"[^A-Za-z0-9_]+", "_", name)

def retry_on_exception(max_retries=3, base_delay=1.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1: raise e
                    time.sleep(base_delay * (2 ** attempt))
            return None
        return wrapper
    return decorator
