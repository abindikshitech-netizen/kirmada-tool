import sys
import os
from loguru import logger
from constants import LOGS_DIR

logger.remove()
logger.add(sys.stdout, format="{time} {level} {message}", level="DEBUG")
logger.add(os.path.join(LOGS_DIR, "system.log"), rotation="10 MB", level="INFO")
logger.add(os.path.join(LOGS_DIR, "failed.log"), rotation="10 MB", level="ERROR")
logger.add(os.path.join(LOGS_DIR, "api.log"), filter=lambda record: record["extra"].get("name") == "API", level="INFO")

app_logger = logger
def get_logger(name):
    return logger.bind(name=name)
