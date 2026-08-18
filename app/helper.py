from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


# Logger for the application
def setup_logger(log_file: Path) -> logging.Logger:
  log_file.parent.mkdir(parents=True, exist_ok=True)
  logger = logging.getLogger("application_logs")
  logger.setLevel(logging.INFO)
  logger.handlers.clear()

  formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")
  console_handler = logging.StreamHandler()
  console_handler.setFormatter(formatter)
  logger.addHandler(console_handler)

  file_handler = logging.FileHandler(log_file, encoding="utf-8")
  file_handler.setFormatter(formatter)
  logger.addHandler(file_handler)
  return logger


# Logger for the summary only
def setup_summary_logger(log_file: Path) -> logging.Logger:
  log_file.parent.mkdir(parents=True, exist_ok=True)

  logger = logging.getLogger("summary_logs")
  logger.setLevel(logging.INFO)
  logger.handlers.clear()
  logger.propagate = False

  formatter = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")

  file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
  file_handler.setFormatter(formatter)
  logger.addHandler(file_handler)

  return logger


# Load articles from a JSON file
def load_storage(path: Path) -> dict[str, dict]:
  if not path.exists():
    return {}
  with path.open("r", encoding="utf-8") as file:
    state = json.load(file)
  if not isinstance(state, dict):
    raise ValueError("State file must contain a JSON object")
  return state


# Save articles to a JSON file
def save_storage(path: Path, state: dict[str, dict]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)

  with NamedTemporaryFile(
          "w",
          encoding="utf-8",
          dir=path.parent,
          prefix=f".{path.name}.",
          delete=False,
  ) as temporary:
    json.dump(state, temporary, indent=2, ensure_ascii=False, sort_keys=True)
    temporary.write("\n")
    temporary_path = Path(temporary.name)
  os.replace(temporary_path, path)


# Hash content for comparison
def calculate_sha256(content: str) -> str:
  normalized = content.replace("\r\n", "\n").strip()
  return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# Detect status of an article use HASH
def detect_status(previous: dict | None, new_hash: str) -> str:
  if previous is None:
    return "added"
  if previous.get("hash") != new_hash:
    return "updated"
  return "skipped"
