import time
import threading

class PerformanceTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.start_time = 0
        self.total_shops = 0
        self.processed_shops = 0
        self.success_count = 0
        self.failed_count = 0
        self.manual_count = 0
        self.api_calls = 0
        self.playwright_calls = 0
        
    def start(self, total):
        self.start_time = time.time()
        self.total_shops = total
        self.processed_shops = 0
        
    def record_success(self):
        with self.lock:
            self.processed_shops += 1
            self.success_count += 1
            
    def record_manual(self):
        with self.lock:
            self.processed_shops += 1
            self.manual_count += 1
            
    def record_failed(self):
        with self.lock:
            self.processed_shops += 1
            self.failed_count += 1
            
    def record_api_call(self):
        with self.lock: self.api_calls += 1
        
    def record_playwright_call(self):
        with self.lock: self.playwright_calls += 1
        
    def get_stats(self):
        with self.lock:
            elapsed = time.time() - self.start_time
            speed = self.processed_shops / elapsed if elapsed > 0 else 0
            eta = (self.total_shops - self.processed_shops) / speed if speed > 0 else 0
            return {
                "elapsed_seconds": elapsed,
                "speed_shops_per_sec": speed,
                "eta_seconds": eta,
                "processed_shops": self.processed_shops,
                "total_shops": self.total_shops,
                "success_count": self.success_count,
                "failed_count": self.failed_count,
                "manual_count": self.manual_count,
                "api_calls": self.api_calls,
                "playwright_calls": self.playwright_calls
            }

perf_tracker = PerformanceTracker()
