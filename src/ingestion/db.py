from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg


def connection_info() -> dict[str, str]:
  return {
    "host": os.environ.get("FRAGMENT_DB_HOST", "localhost"),
    "port": os.environ.get("FRAGMENT_DB_PORT", "55432"),
    "dbname": os.environ.get("FRAGMENT_DB_NAME", "fragment"),
    "user": os.environ.get("FRAGMENT_DB_USER", "fragment"),
    "password": os.environ.get("FRAGMENT_DB_PASSWORD", "fragment_dev_password"),
  }


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
  with psycopg.connect(**connection_info()) as conn:
    yield conn
