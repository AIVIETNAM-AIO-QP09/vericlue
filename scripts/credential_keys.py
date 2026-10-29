"""Quản lý public pin BBS trong DB; không đọc/sinh/đổi khóa bí mật hoặc cấu hình.

uv run python scripts/credential_keys.py --issuer https://vericlue.example register --public-key <path>
uv run python scripts/credential_keys.py --issuer https://vericlue.example activate --key-id <sha256>
uv run python scripts/credential_keys.py --issuer https://vericlue.example revoke --key-id <sha256>
uv run python scripts/credential_keys.py --issuer https://vericlue.example list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))


def main(argv: list[str] | None = None) -> int:
    """Apply one explicitly requested operator action to the configured database."""
    from sqlalchemy import select, text

    from vericlue_api.core.config import Settings
    from vericlue_api.db.database import Database
    from vericlue_api.db.models import CredentialTrustKeyRow, aware
    from vericlue_api.schemas.credential import CredentialKey
    from vericlue_api.services.credential_keys import CredentialKeyRegistry

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issuer", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="Đăng ký public pin chờ kích hoạt")
    register.add_argument("--public-key", type=Path, required=True)
    for name in ("activate", "revoke"):
        command = commands.add_parser(name)
        command.add_argument("--key-id", required=True)
    commands.add_parser("list", help="Xem metadata công khai; không in public/private key")
    args = parser.parse_args(argv)
    database = None
    try:
        settings = Settings()
        database = Database(settings.database_url)
        with database.sessions.begin() as db:
            if args.command != "list":
                if db.bind.dialect.name == "sqlite":
                    db.execute(text("BEGIN IMMEDIATE"))
                elif db.bind.dialect.name == "postgresql":
                    db.execute(
                        text("SELECT set_config('lock_timeout', :timeout, true)"),
                        {"timeout": f"{max(1, round(settings.db_lock_timeout_seconds * 1000))}ms"},
                    )
            registry = CredentialKeyRegistry(db, args.issuer)
            if args.command == "register":
                path = args.public_key
                if not path.is_file() or path.stat().st_size > 2048:
                    raise ValueError("Invalid public pin file")
                raw = json.loads(path.read_bytes())
                if not isinstance(raw, dict) or set(raw) != {"algorithm", "key_id", "public_key"}:
                    raise ValueError("Only a public pin is accepted")
                registry.register(CredentialKey.model_validate(raw))
            elif args.command == "activate":
                registry.activate(args.key_id)
            elif args.command == "revoke":
                registry.revoke(args.key_id)
            rows = db.scalars(
                select(CredentialTrustKeyRow)
                .where(CredentialTrustKeyRow.issuer == args.issuer)
                .order_by(CredentialTrustKeyRow.key_id)
            )
            output = [
                {
                    "issuer": row.issuer,
                    "key_id": row.key_id,
                    "state": row.state,
                    "verify_until": aware(row.verify_until).isoformat()
                    if row.verify_until
                    else None,
                    "created_at": aware(row.created_at).isoformat(),
                    "changed_at": aware(row.changed_at).isoformat(),
                }
                for row in rows
            ]
        # Commit must succeed before reporting the new trust state.
        print(json.dumps({"keys": output}, ensure_ascii=True))
        return 0
    except Exception:
        print(
            "Không thực hiện được thay đổi khóa. Kiểm tra cấu hình DB, migration, issuer và public pin.",
            file=sys.stderr,
        )
        return 2
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
