import json
import os
import threading
from address_parser import AddressParser
from constants import CACHE_FILE

class CacheManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.cache = {}
        self.load()
    def load(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f: self.cache = json.load(f)
            except: pass
    def save(self):
        with self.lock:
            try:
                with open(CACHE_FILE, "w") as f: json.dump(self.cache, f)
            except: pass
    def get_cache_key(self, name, district):
        return f"{AddressParser.normalize_address(name)}_{AddressParser.normalize_address(district)}"
    def get(self, name, district):
        with self.lock: return self.cache.get(self.get_cache_key(name, district))
    def set(self, shop):
        with self.lock:
            self.cache[self.get_cache_key(shop.original_shop_name_address, shop.original_district)] = shop.to_dict()
cache = CacheManager()
