import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, rec: logging.LogRecord) -> str:
        payload = {"level": rec.levelname, "msg": rec.getMessage(), "logger": rec.name}
        return json.dumps(payload, ensure_ascii=True)


def get_logger(name: str = "app") -> logging.Logger:
    lg = logging.getLogger(name)
    if not lg.handlers:
        h = logging.StreamHandler()
        h.setFormatter(JsonFormatter())
        lg.addHandler(h)
        lg.setLevel(logging.INFO)
    return lg
