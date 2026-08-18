from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI


class OpenAIVectorStore:
  def __init__(self, api_key: str, vector_store_id: str, logger: logging.Logger) -> None:
    self.client = OpenAI(api_key=api_key)
    self.vector_store_id = vector_store_id
    self.logger = logger

  def upload_async(self, path: Path) -> str:
    uploaded_file_id: str | None = None

    self.logger.info("openai_upload_started file=%s vector_store_id=%s", path, self.vector_store_id)

    try:
      with path.open("rb") as stream:
        uploaded_file = self.client.files.create(file=stream, purpose="assistants")

      uploaded_file_id = uploaded_file.id

      self.logger.info("openai_file_created file=%s file_id=%s", path, uploaded_file_id)

      self.logger.info(
        "vector_store_indexing_started "
        "file_id=%s vector_store_id=%s",
        uploaded_file_id,
        self.vector_store_id,
      )

      vector_file = self.client.vector_stores.files.create_and_poll(vector_store_id=self.vector_store_id,
                                                                    file_id=uploaded_file_id)

      self.logger.info(
        "vector_store_indexing_finished "
        "file_id=%s status=%s",
        uploaded_file_id,
        vector_file.status,
      )

      if vector_file.status != "completed":
        raise RuntimeError(
          "Vector Store indexing did not complete: "
          f"status={vector_file.status}, "
          f"error={vector_file.last_error}"
        )

      self.logger.info(
        "openai_upload_completed "
        "file=%s file_id=%s vector_store_id=%s",
        path,
        uploaded_file_id,
        self.vector_store_id,
      )

      return uploaded_file_id

    except Exception:
      self.logger.exception(
        "openai_upload_failed "
        "file=%s file_id=%s vector_store_id=%s",
        path,
        uploaded_file_id,
        self.vector_store_id,
      )

      if uploaded_file_id:
        try:
          self.client.files.delete(uploaded_file_id)

          self.logger.info("openai_failed_file_deleted file_id=%s", uploaded_file_id)
        except Exception:
          self.logger.exception("openai_failed_file_cleanup_failed file_id=%s", uploaded_file_id)

      raise
