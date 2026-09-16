"""Run integration tests only against an isolated PostgreSQL database."""

import os
import subprocess
import sys

import psycopg
from evaldock.config import settings

url = settings().queue_url
with psycopg.connect(url, autocommit=True) as connection:
    if not connection.execute("SELECT 1 FROM pg_database WHERE datname='evaldock_test'").fetchone():
        connection.execute("CREATE DATABASE evaldock_test")
env = {**os.environ, "DATABASE_URL": settings().database_url.rsplit("/", 1)[0] + "/evaldock_test"}
subprocess.run(["uv", "run", "alembic", "upgrade", "head"], env=env, check=True)
sys.exit(subprocess.run(["uv", "run", "pytest", "-q", *sys.argv[1:]], env=env).returncode)
