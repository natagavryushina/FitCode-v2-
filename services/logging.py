import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO") -> None:
	log_level = getattr(logging, level.upper(), logging.INFO)
	root = logging.getLogger()
	root.setLevel(log_level)

	# Clear existing handlers in case of reload
	root.handlers.clear()

	handler = logging.StreamHandler(sys.stdout)
	handler.setLevel(log_level)
	formatter = logging.Formatter(
		fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
		datefmt="%Y-%m-%d %H:%M:%S",
	)
	handler.setFormatter(formatter)
	root.addHandler(handler)

	# Reduce noise from third-party libs
	logging.getLogger("aiogram").setLevel(log_level)
	logging.getLogger("httpx").setLevel(logging.WARNING)