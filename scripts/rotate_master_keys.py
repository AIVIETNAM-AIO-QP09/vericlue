"""Offline DEK rewrap; keys and database URL are never accepted inline or printed."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from contextlib import suppress
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default includes unrecognized argument values, possibly secrets.
        print(json.dumps({"error_code": "invalid_arguments"}))
        raise SystemExit(2)


def env_value(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name):
        raise ValueError("invalid_environment_name")
    value = os.environ.get(name)
    if not value:
        raise ValueError("missing_environment_value")
    return value


def read_master(path: str | None, env: str | None) -> bytes:
    """Read a canonical base64 master key without logging its input location."""
    if path:
        key_path = Path(path)
        if not key_path.is_file():
            raise ValueError("regular_key_file_required")
        with key_path.open("rb") as f:
            raw = f.read(129)
    else:
        if env is None:
            raise ValueError("key_input_required")
        raw = env_value(env).encode("ascii")
    if len(raw) > 128:
        raise ValueError("invalid_key_input")
    encoded = raw.strip()
    key = base64.b64decode(encoded, validate=True)
    if len(key) != 32 or base64.b64encode(key) != encoded:
        raise ValueError("invalid_key_input")
    return key


def database_for(url_text: str, *, apply: bool):
    from sqlalchemy.engine import make_url

    from vericlue_api.db.database import Database

    url = make_url(url_text)
    backend = url.get_backend_name()
    if backend not in {"sqlite", "postgresql"}:
        raise ValueError("unsupported_database")
    if backend == "sqlite":
        if not url.database or url.database == ":memory:" or url.query:
            raise ValueError("existing_sqlite_database_required")
        path = Path(url.database).resolve()
        if not path.is_file():
            raise ValueError("existing_sqlite_database_required")
        # Never create an empty DB on a mistyped dry run. Reject live WAL/journal
        # stores: use a consistent offline copy; do not ignore uncheckpointed data.
        for suffix in ("-wal", "-shm", "-journal"):
            if Path(str(path) + suffix).exists():
                raise ValueError("offline_sqlite_snapshot_required")
        database = "file:" + quote(path.as_posix(), safe="/:")
        url = url.set(database=database, query={"mode": "rw" if apply else "ro", "uri": "true"})
    return Database(url.render_as_string(hide_password=False))


def main(argv: list[str] | None = None) -> int:
    from vericlue_api.core.key_rotation import KeyRotationError, rewrap_master_keys

    parser = SafeParser(description=__doc__)
    old = parser.add_mutually_exclusive_group(required=True)
    old.add_argument("--old-master-file")
    old.add_argument("--old-master-env")
    new = parser.add_mutually_exclusive_group(required=True)
    new.add_argument("--new-master-file")
    new.add_argument("--new-master-env")
    parser.add_argument(
        "--database-env",
        required=True,
        help="Name of the environment variable containing the DB URL",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-services-stopped", action="store_true")
    args = parser.parse_args(argv)
    database = None
    try:
        if args.apply and not args.confirm_services_stopped:
            raise KeyRotationError("services_stopped_confirmation_required")
        old_key = read_master(args.old_master_file, args.old_master_env)
        new_key = read_master(args.new_master_file, args.new_master_env)
        if old_key == new_key:
            raise KeyRotationError("master_keys_equal")
        database = database_for(env_value(args.database_env), apply=args.apply)
        report = rewrap_master_keys(
            database,
            old_key,
            new_key,
            apply=args.apply,
            services_stopped=args.confirm_services_stopped,
        )
        print(json.dumps(report))
        return 0
    except KeyRotationError as e:
        print(json.dumps({"error_code": e.code}))
        return 2
    except Exception:
        print(json.dumps({"error_code": "rotation_input_or_database_invalid"}))
        return 2
    finally:
        if database is not None:
            # Rotation status was decided by its transaction. Pool cleanup must
            # not expose driver details or override a committed result.
            with suppress(Exception):
                database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
