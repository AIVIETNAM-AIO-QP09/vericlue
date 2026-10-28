"""Read-only counts for MEDIA_DIR/_decoded; does not identify or delete live leases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "scripts")]


def main(argv: list[str] | None = None) -> int:
    from rotate_master_keys import SafeParser, env_value

    from vericlue_api.core.key_rotation import KeyRotationError, inventory_private_temp

    parser = SafeParser(description=__doc__)
    parser.add_argument("--media-dir-env", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(inventory_private_temp(env_value(args.media_dir_env))))
        return 0
    except KeyRotationError as e:
        print(json.dumps({"error_code": e.code}))
        return 2
    except Exception:
        print(json.dumps({"error_code": "temp_inventory_failed"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
