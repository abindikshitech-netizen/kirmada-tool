import json
import os
from constants import BASE_DIR
class AppSettings:
    def __init__(self):
        self.path = os.path.join(BASE_DIR, "settings.json")
        self.data = {"concurrency": 5, "delay": 1.0}
        self.load()
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self.data.update(json.load(f))
            except: pass
    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f)
    def get(self, key, default=None): return self.data.get(key, default)
    def set(self, key, val):
        self.data[key] = val
        self.save()
    def get_api_key(self): return self.get("api_key", "")
    def set_api_key(self, key, remember):
        if remember: self.set("api_key", key)
        else: self.set("api_key", "")
app_settings = AppSettings()
