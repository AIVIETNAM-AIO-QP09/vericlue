"""Validate iOS Release configuration/artifact; never contacts a server or prints tokens."""

from __future__ import annotations

import argparse
import os
import plistlib
from pathlib import Path
from urllib.parse import urlsplit


def valid_endpoint(raw: str) -> bool:
    try:
        url = urlsplit(raw)
        return bool(
            raw
            and not any(char.isspace() for char in raw)
            and not any(marker in raw for marker in ("<", ">", "$("))
            and url.scheme == "https"
            and url.hostname
            and url.username is None
            and url.password is None
            and not url.query
            and not url.fragment
            and (url.port is None or 1 <= url.port <= 65535)
        )
    except ValueError:
        return False


def check_artifact(app: Path) -> list[str]:
    with (app / "Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    errors = []
    if not valid_endpoint(info.get("API_BASE_URL", "")):
        errors.append(
            "API_BASE_URL must be a configured HTTPS URL, without credentials/query/fragment."
        )
    if info.get("NSAppTransportSecurity"):
        errors.append("Release must not carry ATS exceptions.")
    if "NSLocalNetworkUsageDescription" in info:
        errors.append("Release still contains the Debug local-network description.")
    if not info.get("NSCameraUsageDescription") or not info.get("NSMicrophoneUsageDescription"):
        errors.append("Missing camera/microphone permission descriptions.")
    fonts = info.get("UIAppFonts", [])
    if len(fonts) != 4 or any(not (app / font).is_file() for font in fonts):
        errors.append("The four Be Vietnam Pro fonts are not bundled correctly.")
    executable = app / info["CFBundleExecutable"]
    binary = executable.read_bytes()
    for marker in (
        b"debug-gallery-button",
        b"debug-front-camera-checkpoint",
        b"debug-device-key-checkpoint",
        b"X-Mock-Scenario",
        b"--vc-navigation-trace",
        b"--vc-theme",
        b"--vc-text-size",
    ):
        if marker in binary:
            errors.append("Release binary contains a Debug-only marker: " + marker.decode())
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app", type=Path, help="Built Release .app; checks the artifact, not source files"
    )
    args = parser.parse_args()
    try:
        if args.app:
            errors = check_artifact(args.app)
        elif os.environ.get("CONFIGURATION") == "Release":
            errors = (
                []
                if valid_endpoint(os.environ.get("API_BASE_URL", ""))
                else [
                    "Release requires API_BASE_URL=https://<approved-host>/; configure Release.local.xcconfig "
                    "or pass the build setting. HTTP, placeholders and credentials are not allowed."
                ]
            )
        else:
            print("Debug: Release endpoint guard not applicable.")
            return 0
    except (OSError, ValueError, KeyError, plistlib.InvalidFileException):
        errors = ["Unable to inspect Release artifact. Check the .app path and Info.plist."]
    for error in errors:
        print("error: " + error)
    if not errors:
        print(
            "Release static checks passed; this does NOT verify DNS, TLS, API compatibility or device acceptance."
        )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
