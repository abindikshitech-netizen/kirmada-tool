import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
INPUT_DIR = os.path.join(BASE_DIR, "input")
CACHE_FILE = os.path.join(BASE_DIR, "cache", "shops.db")
API_TIMEOUT = 15
PLAYWRIGHT_TIMEOUT = 30000
MAX_RETRIES = 3
STATUS_MANUAL_REVIEW = "Manual Review"

for d in [ASSETS_DIR, SCREENSHOTS_DIR, LOGS_DIR, TEMP_DIR, REPORTS_DIR, OUTPUT_DIR, INPUT_DIR, os.path.dirname(CACHE_FILE)]:
    os.makedirs(d, exist_ok=True)
