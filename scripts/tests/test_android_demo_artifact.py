"""The CI artifact must reject a gallery-only build before publication/signing."""

import json
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/android-app.yml"


@pytest.fixture
def artifact_check(tmp_path, monkeypatch):
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    step = next(
        step
        for step in workflow["jobs"]["apk"]["steps"]
        if step.get("name") == "Check package and prepare local signing input"
    )
    script = "\n".join(step["run"].splitlines()[1:-1])
    apk = tmp_path / "app/build/outputs/apk/debug/app-arm64-v8a-debug-unsigned.apk"
    apk.parent.mkdir(parents=True)
    apk.write_bytes(b"synthetic test APK bytes; no signing key")
    tools = tmp_path / "sdk/build-tools/35.0.0"
    (tools / "lib").mkdir(parents=True)
    (tools / "lib/apksigner.jar").write_bytes(b"synthetic SDK fixture")
    (tools / "NOTICE.txt").write_text("synthetic notice")
    config = tmp_path / "app/build/generated/BuildConfig.java"
    config.parent.mkdir(parents=True)
    for name, value in {
        "ANDROID_HOME": str(tmp_path / "sdk"),
        "VERICLUE_API_BASE_URL": "http://localhost:8421/",
        "GITHUB_SHA": "a" * 40,
        "SOURCE_HEAD_SHA": "b" * 40,
        "GITHUB_RUN_ID": "1234",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *a, **k: "package: name='vn.vericlue.app'\napplication-label:'VeriClue'\n",
    )

    def check(live: bool):
        config.write_text(
            'String API_BASE_URL = "http://localhost:8421/";\n'
            "boolean SIGNED_MEDIA = true;\n"
            f"boolean LIVE_API_DEFAULT = {str(live).lower()};\n"
        )
        exec(compile(script, str(WORKFLOW), "exec"), {})

    return check


def test_gallery_only_apk_never_becomes_a_demo_artifact(artifact_check, tmp_path):
    with pytest.raises(AssertionError):
        artifact_check(False)
    assert not (tmp_path / "vericlue-build").exists()


def test_live_api_artifact_records_its_default_mode(artifact_check, tmp_path):
    artifact_check(True)
    info = json.loads((tmp_path / "vericlue-build/build-info.json").read_text())
    assert info["live_by_default"] is True
    assert info["signed_media"] is True
    assert info["signing"] == "required_on_laptop"
