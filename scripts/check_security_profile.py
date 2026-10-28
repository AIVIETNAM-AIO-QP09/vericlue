"""Read-only profile preflight; never generate keys or connect to DB/models."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))


def main() -> int:
    """Print safe status metadata, excluding configuration values and exception text."""
    from vericlue_api.core.config import Settings
    from vericlue_api.core.security_profile import security_profile_checks

    try:
        settings = Settings()
        protected = settings.security_profile == "protected"
        checks = security_profile_checks(settings)
        ready = protected and all(checks.values())
        print(
            json.dumps(
                {
                    "profile": settings.security_profile,
                    "status": "protected_configuration_ok"
                    if ready
                    else "synthetic"
                    if not protected
                    else "configuration_invalid",
                    "protected_configuration_ok": ready,
                    "checks": checks,
                    "not_checked": [
                        "app_signed_media_build",
                        "biometric_acceptance",
                        "ui_consent",
                        "tls_proxy",
                        "filesystem_permissions",
                        "backup_retention",
                        "credential_runtime",
                    ],
                }
            )
        )
        return 0 if not protected or ready else 2
    except Exception:
        print(json.dumps({"status": "configuration_invalid", "protected_configuration_ok": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
