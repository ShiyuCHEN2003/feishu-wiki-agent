import json
import os
from models import LogEntry

_DEFAULT_LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "operations.json")


class Logger:
    def __init__(self, log_path: str = _DEFAULT_LOG_PATH) -> None:
        self._path = log_path
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)

    def record(self, entry: LogEntry) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def read_recent(self, n: int = 20) -> list[dict]:
        if not os.path.exists(self._path):
            return []
        with open(self._path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        entries = [json.loads(l) for l in lines]
        return list(reversed(entries[-n:]))
