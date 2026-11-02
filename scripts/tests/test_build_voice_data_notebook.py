"""Execute generated notebook code against bounded offline publisher fixtures."""

import importlib
import io
import json
from pathlib import Path

import pytest

from scripts.tests.test_prepare_nes2net_data import sources


def test_generated_cloud_cell_runs_audited_preparation_without_external_dependencies(
    tmp_path, monkeypatch
):
    builder = importlib.import_module("scripts.build_voice_data_notebook")
    _, payloads = sources()

    def urlopen(request, **kwargs):
        name = request.full_url.split(builder.REVISION + "/", 1)[1]
        return io.BytesIO(payloads[name])

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setenv("VERICLUE_DATA_OUTPUT", str(tmp_path / "cloud-bundle"))
    source = (Path(__file__).parents[1] / "prepare_nes2net_data.py").read_text("utf-8")
    document = builder.build(source, "a" * 40, dirty=False)
    scope = {}
    exec(compile("".join(document["cells"][1]["source"]), "<cloud-cell>", "exec"), scope)
    assert scope["report"]["sample_count"] == 4
    assert scope["report"]["calibration_ready"] is False
    assert scope["archive"].is_file()
    assert scope["report"]["source_commit"] == "a" * 40
    assert json.loads((tmp_path / "cloud-bundle/manifest.json").read_text())["samples"]


def test_dirty_embedded_source_refuses_to_fetch_or_run(tmp_path, monkeypatch):
    builder = importlib.import_module("scripts.build_voice_data_notebook")
    monkeypatch.setenv("VERICLUE_DATA_OUTPUT", str(tmp_path / "must-not-exist"))
    document = builder.build(
        "raise AssertionError('source must not execute')", "a" * 40, dirty=True
    )
    with pytest.raises(ValueError):
        exec(compile("".join(document["cells"][1]["source"]), "<cloud-cell>", "exec"), {})
    assert not (tmp_path / "must-not-exist").exists()
