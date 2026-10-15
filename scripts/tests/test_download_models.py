"""DATA-02 downloader checks with local HTTP fixtures, never external weights."""

import copy
import hashlib
import importlib.util
import os
import subprocess
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "download_models", ROOT / "scripts/download_models.py"
)
dl = importlib.util.module_from_spec(SPEC)
sys.modules["download_models"] = dl
SPEC.loader.exec_module(dl)
PAYLOAD = b"synthetic offline weights\x00\x01" * 17


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def server():
    routes = {"/weights": {"body": PAYLOAD}}
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            route = routes[self.path]
            self.send_response(200)
            self.send_header("Content-Type", route.get("content_type", "application/octet-stream"))
            self.send_header("Content-Length", str(route.get("length", len(route["body"]))))
            self.end_headers()
            self.wfile.write(route["body"])
            self.close_connection = True

        def log_message(self, *_args):
            pass

    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=instance.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{instance.server_port}", routes, requests
    finally:
        instance.shutdown()
        instance.server_close()
        worker.join()


@pytest.fixture
def manifest(tmp_path, monkeypatch, server):
    base_url, _, _ = server
    storage = tmp_path / "weights-store"
    monkeypatch.setenv("MODELS_DIR", str(storage))
    path = tmp_path / "manifest.yaml"
    model = {
        "id": "tiny",
        "purpose": "Offline test",
        "source": {"type": "http", "revision": "fixture-v1"},
        "license": "MIT",
        "license_url": "https://example.invalid/license",
        "license_status": "verified",
        "status": "ready",
        "files": [
            {
                "path": "weights.bin",
                "url": f"{base_url}/weights",
                "size_bytes": len(PAYLOAD),
                "sha256": None,
                "upstream_sha256": None,
            }
        ],
    }
    path.write_text(yaml.safe_dump({"models": [model]}), encoding="utf-8")
    return path, storage, model


def save(path, models):
    path.write_text(yaml.safe_dump({"models": models}), encoding="utf-8")


def loaded(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))["models"]


def run(path, *options):
    return dl.main(["--manifest", str(path), *options])


def test_first_download_records_hash_then_skips_valid(manifest, server):
    path, storage, _ = manifest
    assert run(path) == 0
    assert (storage / "tiny/weights.bin").read_bytes() == PAYLOAD
    assert loaded(path)[0]["files"][0]["sha256"] == digest(PAYLOAD)
    count = len(server[2])
    assert run(path) == 0
    assert len(server[2]) == count
    assert not (storage / "tiny/weights.bin.part").exists()


def test_verify_is_offline_and_detects_corruption(manifest, server, monkeypatch):
    path, storage, _ = manifest
    assert run(path) == 0
    before = path.read_bytes()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("verify must never download")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    if hasattr(dl, "urlopen"):
        monkeypatch.setattr(dl, "urlopen", forbidden)
    assert run(path, "--verify") == 0
    target = storage / "tiny/weights.bin"
    target.write_bytes(b"corrupted")
    assert run(path, "--verify") != 0
    assert run(path) != 0
    assert path.read_bytes() == before
    assert target.read_bytes() == b"corrupted"
    assert len(server[2]) == 1


@pytest.mark.parametrize("state", ["missing_file", "missing_hash"])
def test_verify_missing_is_error_without_network(manifest, server, state):
    path, storage, model = manifest
    if state == "missing_file":
        model["files"][0]["sha256"] = digest(PAYLOAD)
        save(path, [model])
    else:
        target = storage / "tiny/weights.bin"
        target.parent.mkdir(parents=True)
        target.write_bytes(PAYLOAD)
    before = path.read_bytes()
    assert run(path, "--verify") != 0
    assert not server[2]
    assert path.read_bytes() == before


def test_unpinned_existing_file_redownloads(manifest, server):
    path, storage, _ = manifest
    target = storage / "tiny/weights.bin"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"untrusted existing bytes")
    assert run(path) == 0
    assert server[2] == ["/weights"]
    assert target.read_bytes() == PAYLOAD


def test_interruption_persists_completed_file_and_retries_remaining(manifest, server):
    path, storage, model = manifest
    base_url, routes, requests = server
    routes["/second"] = {"body": PAYLOAD[:10], "length": len(PAYLOAD)}
    model["files"].append(
        {
            "path": "second.bin",
            "url": f"{base_url}/second",
            "size_bytes": len(PAYLOAD),
            "sha256": None,
            "upstream_sha256": None,
        }
    )
    save(path, [model])
    assert run(path) != 0
    files = loaded(path)[0]["files"]
    assert files[0]["sha256"] == digest(PAYLOAD)
    assert files[1]["sha256"] is None
    assert (storage / "tiny/weights.bin").read_bytes() == PAYLOAD
    assert not (storage / "tiny/second.bin").exists()
    routes["/second"] = {"body": PAYLOAD}
    assert run(path) == 0
    assert requests.count("/weights") == 1
    assert requests.count("/second") == 2
    assert loaded(path)[0]["files"][1]["sha256"] == digest(PAYLOAD)


@pytest.mark.parametrize("failure", ["size", "upstream_hash", "html"])
def test_failed_download_never_records_hash_or_final_file(manifest, server, failure):
    path, storage, model = manifest
    if failure == "size":
        model["files"][0]["size_bytes"] = len(PAYLOAD) + 1
    elif failure == "upstream_hash":
        model["files"][0]["upstream_sha256"] = "0" * 64
    else:
        server[1]["/weights"] = {
            "body": b"<!doctype html><html>login</html>",
            "content_type": "text/html",
        }
        model["files"][0]["size_bytes"] = len(server[1]["/weights"]["body"])
    save(path, [model])
    before = path.read_bytes()
    assert run(path) != 0
    assert path.read_bytes() == before
    assert not (storage / "tiny/weights.bin").exists()


def test_unknown_id_is_error_without_network(manifest, server):
    assert run(manifest[0], "--only", "missing") != 0
    assert not server[2]


@pytest.mark.parametrize("body", ["[broken", "models: nope", '{"models": [1]}'])
def test_malformed_manifest_is_error_without_network(manifest, server, body):
    path = manifest[0]
    path.write_text(body, encoding="utf-8")
    assert run(path) != 0
    assert not server[2]


@pytest.mark.parametrize(
    "license_name,status", [("MIT", "pending"), ("GPL-3.0", "verified"), ("unknown", "verified")]
)
def test_unapproved_license_blocks_before_network(manifest, server, license_name, status):
    path, _, model = manifest
    model["license"], model["license_status"] = license_name, status
    save(path, [model])
    assert run(path, "--only", "tiny") != 0
    assert not server[2]


def test_default_skips_deferred_but_explicit_blocked_fails(manifest, server):
    path, _, model = manifest
    deferred = copy.deepcopy(model)
    deferred["id"], deferred["status"] = "later", "deferred"
    blocked = copy.deepcopy(model)
    blocked["id"], blocked["status"] = "blocked", "blocked"
    save(path, [model, deferred, blocked])
    assert run(path) == 0
    assert len(server[2]) == 1
    assert run(path, "--only", "blocked") != 0
    assert len(server[2]) == 1


@pytest.mark.parametrize(
    "bad_path",
    [
        "../escape.bin",
        "/absolute.bin",
        "C:/escape.bin",
        "nested/../../escape.bin",
        "../manifest.yaml",
    ],
)
def test_path_traversal_blocks_before_network(manifest, server, bad_path):
    path, _, model = manifest
    model["files"][0]["path"] = bad_path
    save(path, [model])
    assert run(path) != 0
    assert not server[2]


def test_symlink_escape_blocks_before_network(manifest, server, tmp_path):
    path, storage, _ = manifest
    outside = tmp_path / "outside"
    outside.mkdir()
    storage.mkdir()
    try:
        (storage / "tiny").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Platform cannot create directory symlinks without privileges")
    assert run(path) != 0
    assert not server[2]
    assert not (outside / "weights.bin").exists()


def test_default_paths_use_checkout_root_not_working_directory(manifest, monkeypatch, tmp_path):
    path, _, _ = manifest
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    monkeypatch.setattr(dl, "ROOT", checkout)
    monkeypatch.setattr(dl, "MANIFEST", path)
    monkeypatch.delenv("MODELS_DIR")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert dl.models_dir() == (checkout / "models").resolve()
    assert dl.main([]) == 0
    assert (checkout / "models/tiny/weights.bin").read_bytes() == PAYLOAD
    monkeypatch.setenv("MODELS_DIR", "custom-weights")
    assert dl.models_dir() == (checkout / "custom-weights").resolve()


def test_explicit_deferred_drive_download_records_unknown_size(manifest, monkeypatch, server):
    path, storage, model = manifest
    model["status"] = "deferred"
    model["source"] = {"type": "gdrive", "revision": "chưa pin"}
    model["license"], model["license_status"] = "research-only (nc)", "accepted-research"
    item = model["files"][0]
    item["url"], item["size_bytes"] = "https://drive.google.com/uc?id=synthetic", None
    save(path, [model])
    calls = []

    class Response:
        headers = {"Content-Type": "application/octet-stream"}

        def __init__(self):
            self.finished = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self, _size):
            if self.finished:
                return b""
            self.finished = True
            return PAYLOAD

    def open_drive(request, **_kwargs):
        calls.append(request.full_url)
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", open_drive)
    assert run(path, "--only", "tiny") == 0
    assert calls == [item["url"]]
    assert not server[2]
    artifact = loaded(path)[0]["files"][0]
    assert artifact["size_bytes"] == len(PAYLOAD)
    assert artifact["sha256"] == digest(PAYLOAD)
    assert (storage / "tiny/weights.bin").read_bytes() == PAYLOAD


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid/weights",
        "file:///etc/passwd",
        "https://user:password@example.invalid/weights",
    ],
)
def test_unsafe_source_url_blocked_before_network(manifest, server, url):
    path, _, model = manifest
    model["files"][0]["url"] = url
    save(path, [model])
    assert run(path) != 0
    assert not server[2]


@pytest.mark.parametrize("target_kind", ["manifest", "artifact", "partial"])
def test_report_collision_fails_before_network_without_overwrite(manifest, server, target_kind):
    path, storage, _ = manifest
    target = {
        "manifest": path,
        "artifact": storage / "tiny/weights.bin",
        "partial": storage / "tiny/weights.bin.part",
    }[target_kind]
    if target != path:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"protected existing bytes")
    manifest_before, target_before = path.read_bytes(), target.read_bytes()
    assert run(path, "--report", str(target)) != 0
    assert not server[2]
    assert path.read_bytes() == manifest_before
    assert target.read_bytes() == target_before


def test_report_symlink_alias_manifest_preserves_bytes(manifest, server, tmp_path):
    path = manifest[0]
    alias = tmp_path / "report-alias.json"
    try:
        alias.symlink_to(path)
    except (OSError, NotImplementedError):
        pytest.skip("Platform cannot create file symlinks without privileges")
    before = path.read_bytes()
    assert run(path, "--report", str(alias)) != 0
    assert not server[2]
    assert alias.is_symlink() and path.read_bytes() == before


def test_manifest_used_as_artifact_fails_before_network(manifest, server):
    path, storage, _ = manifest
    artifact = storage / "tiny/weights.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(path.read_bytes())
    before = artifact.read_bytes()
    assert run(artifact) != 0
    assert not server[2]
    assert artifact.read_bytes() == before


@pytest.mark.parametrize("collision", ["duplicate", "partial", "unselected_model"])
def test_global_artifact_collision_rejected_before_network(manifest, server, collision):
    path, storage, model = manifest
    if collision == "unselected_model":
        other = copy.deepcopy(model)
        other["id"], other["status"] = "other", "deferred"
        # Symlink two model directories together to expose cross-model collision.
        target = storage / "tiny"
        target.mkdir(parents=True)
        try:
            (storage / "other").symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Platform cannot create directory symlinks without privileges")
        save(path, [model, other])
    else:
        duplicate = copy.deepcopy(model["files"][0])
        if collision == "partial":
            duplicate["path"] += ".part"
        model["files"].append(duplicate)
        save(path, [model])
    before = path.read_bytes()
    assert run(path, "--only", "tiny") != 0
    assert not server[2]
    assert path.read_bytes() == before


def test_cli_help_handles_cp1252_environment():
    environment = os.environ | {"PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/download_models.py"), "--help"],
        env=environment,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert b"--verify" in result.stdout and b"--report" in result.stdout
