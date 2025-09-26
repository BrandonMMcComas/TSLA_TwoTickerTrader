
import logging
import sys
from pathlib import Path


def setup_logging():
    Path("logs").mkdir(exist_ok=True, parents=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/app.log", encoding="utf-8")
        ]
    )
    return logging.getLogger("swingbot")
