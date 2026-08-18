from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from app.helper import (
  calculate_sha256,
  detect_status,
  load_storage,
  save_storage,
  setup_logger,
  setup_summary_logger,
)
from app.openai_store import OpenAIVectorStore
from app.zendesk import ZendeskClient


def main() -> int:
  load_dotenv()

  # LOAD ENVIRONMENT VARIABLES
  zendesk_base_url = os.getenv("ZENDESK_BASE_URL", "https://support.optisigns.com").rstrip("/")
  zendesk_locale = os.getenv("ZENDESK_LOCALE", "en-us")
  article_limit = int(os.getenv("ARTICLE_LIMIT", "30"))
  articles_dir = Path(os.getenv("ARTICLES_DIR", "articles"))
  storage_file = Path(os.getenv("STATE_FILE", "data/storage.json"))
  log_file = Path(os.getenv("LOG_FILE", "logs/app.log"))
  summary_log_file = Path(os.getenv("SUMMARY_LOG_FILE", "logs/summary.log"))
  openai_upload_enabled = os.getenv("OPENAI_UPLOAD", "false", ).strip().lower() in {"1", "true", "yes", "on"}
  openai_api_key = os.getenv("OPENAI_API_KEY")
  vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")

  # Init logger
  logger = setup_logger(log_file)
  summary_logger = setup_summary_logger(summary_log_file)

  if openai_upload_enabled and (not openai_api_key or not vector_store_id):
    logger.error("OPENAI_API_KEY or OPENAI_VECTOR_STORE_ID is not set")
    return 1

  openai_store: OpenAIVectorStore | None = None

  if openai_upload_enabled:
    openai_store = OpenAIVectorStore(api_key=openai_api_key or "", vector_store_id=vector_store_id or "", logger=logger)
    logger.info("OpenAI upload is enabled")
  else:
    logger.info("OpenAI upload is disabled")

  logger.info("Scrape started with limit=%s", article_limit)

  zendesk_client = ZendeskClient(base_url=zendesk_base_url, locale=zendesk_locale)
  storage = load_storage(storage_file)
  articles_dir.mkdir(parents=True, exist_ok=True)
  documents = zendesk_client.fetch_documents(article_limit)

  if len(documents) < article_limit:
    logger.warning("Requested=%s fetched=%s", article_limit, len(documents))

  summary = {
    "added": 0,
    "updated": 0,
    "skipped": 0,
  }

  for document in documents:
    temporary_path: Path | None = None

    try:
      digest = calculate_sha256(document.markdown)
      previous = storage.get(document.article_id)
      status = detect_status(previous, digest)

      if status == "skipped":
        summary["skipped"] += 1
        continue

      path = articles_dir / f"{document.article_id}-{document.slug}.md"

      temporary_path = path.with_name(f".{path.stem}.new.md")

      temporary_path.write_text(document.markdown, encoding="utf-8")
      old_openai_file_id = (previous or {}).get("openai_file_id")

      new_openai_file_id: str | None = None

      if openai_store:
        new_openai_file_id = openai_store.upload_async(temporary_path)

      temporary_path.replace(path)
      temporary_path = None

      old_path = (previous or {}).get("markdown_path")

      if old_path and Path(old_path) != path:
        Path(old_path).unlink(missing_ok=True)

      storage[document.article_id] = {
        "title": document.title,
        "slug": document.slug,
        "hash": digest,
        "updated_at": document.updated_at,
        "source_url": document.source_url,
        "markdown_path": str(path),
        "openai_file_id": new_openai_file_id or old_openai_file_id
      }

      save_storage(storage_file, storage)

      summary[status] += 1

    except Exception:
      logger.exception("article_id=%s status=failed", document.article_id)

    finally:
      if temporary_path:
        temporary_path.unlink(missing_ok=True)

  logger.info("Scrape completed summary=%s", json.dumps(summary))
  summary_logger.info(json.dumps(summary))

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
