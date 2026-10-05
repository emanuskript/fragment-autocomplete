"""Shared PostgreSQL connection helpers for local ingestion scripts."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg


def connection_info() -> dict[str, str]:
  """Build local database settings without embedding a repository password."""
  password = os.environ.get("FRAGMENT_DB_PASSWORD")
  if not password:
    raise RuntimeError(
      "FRAGMENT_DB_PASSWORD is required for database access. "
      "Set it in the environment; Docker Compose can also read it from .env."
    )
  return {
    "host": os.environ.get("FRAGMENT_DB_HOST", "localhost"),
    "port": os.environ.get("FRAGMENT_DB_PORT", "55432"),
    "dbname": os.environ.get("FRAGMENT_DB_NAME", "fragment"),
    "user": os.environ.get("FRAGMENT_DB_USER", "fragment"),
    "password": password,
  }


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
  """Yield a psycopg connection using the project-local database defaults."""
  with psycopg.connect(**connection_info()) as conn:
    yield conn
