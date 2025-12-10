import json
import os

class JsonStore:
    def __init__(self, path, default_data=None):
        self.path = path
        self.default_data = default_data or {}

        if not os.path.exists(self.path):
            self.data = self.default_data.copy()
            self._save()
        else:
            self._load()

    def _load(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    def _save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self._save()

    def delete(self, key):
        if key in self.data:
            del self.data[key]
            self._save()

    def append(self, key, value):
        self.data[key].append(value)
        self._save()

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self._save()

    def __contains__(self, key):
        return key in self.data
