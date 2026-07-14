import json
import os
from constants import BASE_DIR
class ResumeState:
    def __init__(self):
        self.path = os.path.join(BASE_DIR, "resume.json")
        self.state = {"processed_rows": []}
        self.load()
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self.state.update(json.load(f))
            except: pass
    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.state, f)
    def mark_processed(self, idx):
        if idx not in self.state["processed_rows"]:
            self.state["processed_rows"].append(idx)
    def is_processed(self, idx):
        return idx in self.state["processed_rows"]
    def clear(self):
        self.state["processed_rows"] = []
        self.save()
resume_state = ResumeState()
