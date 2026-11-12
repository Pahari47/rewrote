import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)