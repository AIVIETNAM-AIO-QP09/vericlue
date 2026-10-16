"""Offline whole-ZIP Zalo downloads, safe extraction, and HTTP 416 recovery."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import sys
import zipfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import data_download_core as core  # noqa: E402
import data_download_images as images  # noqa: E402

ARCHIVE_NAME = "liveness-detection-zalo-2022.zip"
LABEL_PATH = "train/train/label.csv"
LABEL_BYTES = b"fname,liveness_score\nfirst.mp4,0\nsecond.mp4,1\n"
TRAIN = {
    LABEL_PATH: LABEL_BYTES,
    "train/train/videos/first.mp4": b"original-first-video-bytes",
    "train/train/videos/second.mp4": b"original-second-video-bytes",
}
IGNORED = {
    "test/test/videos/test.mp4": b"unlabelled-test-video",
    "unlabelled/videos/unknown.mp4": b"unlabelled-video",
    "train/readme.txt": b"unrelated-documentation",
    "train/train/videos/orphan.mp4": b"train-video-without-label",
}


def zip_bytes(files: dict[str, bytes]) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, contents in files.items():
            archive.writestr(path, contents)
    return payload.getvalue()


class ZaloClient:
    """Return metadata and a fixture archive without any HTTP requests."""

    kaggle_auth = ("fixture-user", "fixture-private-key")
    token = ""

    def __init__(self) -> None:
        self.payload = zip_bytes({**TRAIN, **IGNORED})
        self.calls: list[tuple[str, str]] = []
        self.downloaded: list[core.RemoteFile] = []

    def json(self, url: str, **kwargs: object) -> dict:
        self.calls.append(("metadata", url))
        if "/view/hlly34/liveness-detection-zalo-2022" in url:
            return {
                "currentVersionNumber": 7,
                "totalBytes": sum(map(len, {**TRAIN, **IGNORED}.values())),
            }
        assert "/list/hlly34/liveness-detection-zalo-2022" in url
        return {
            "datasetFiles": [
                {"name": path, "totalBytes": len(payload)}
                for path, payload in {**TRAIN, **IGNORED}.items()
            ]
        }

    def head_size(self, url: str, **kwargs: object) -> int:
        self.calls.append(("size", url))
        assert "datasetVersionNumber=7" in url
        return len(self.payload)

    def get_bytes(self, url: str, **kwargs: object) -> bytes:
        pytest.fail("whole ZIP must not fetch labels or videos individually")

    def download(self, remote: core.RemoteFile, dest: Path) -> None:
        self.downloaded.append(remote)
        assert remote.size == len(self.payload)
        assert "datasetVersionNumber=7" in remote.url
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.payload)


def zalo_dataset(budget: int = 1_000_000_000) -> core.Dataset:
    return core.Dataset(
        "zalo2022",
        "https://www.kaggle.com/datasets/hlly34/liveness-detection-zalo-2022",
        "CC BY-NC 4.0",
        1_000_000,
        budget,
    )


@pytest.mark.parametrize("subset", ["small", "full"])
def test_zalo_prepares_one_version_pinned_zip_without_per_file_downloads(subset: str) -> None:
    client = ZaloClient()
    plan = images.prepare(zalo_dataset(), client, 42, subset)
    assert len(plan.files) == 1
    remote = plan.files[0]
    assert remote.path == ".cache/" + ARCHIVE_NAME
    assert remote.size == len(client.payload)
    assert "datasetVersionNumber=7" in remote.url
    assert plan.revision == "kaggle-version-7"
    assert plan.peak_bytes >= remote.size + sum(map(len, TRAIN.values()))
    assert not client.downloaded
    assert any("/view/" in url for _, url in client.calls)
    assert any("/list/" in url for _, url in client.calls)
    assert len([kind for kind, _ in client.calls if kind == "size"]) == 1
    assert client.kaggle_auth[1] not in " ".join(plan.notes)


@pytest.mark.parametrize("subset", ["small", "full"])
def test_zalo_extracts_only_labelled_train_tree_preserving_paths_and_bytes(
    tmp_path: Path, subset: str
) -> None:
    client = ZaloClient()
    plan = images._prepare_zalo_zip(zalo_dataset(), client, subset)
    assert plan.execute is not None
    plan.execute(tmp_path, client)
    assert len(client.downloaded) == 1
    assert (tmp_path / plan.files[0].path).read_bytes() == client.payload
    for path, contents in TRAIN.items():
        assert (tmp_path / path).read_bytes() == contents
    assert all(not (tmp_path / path).exists() for path in IGNORED)
    assert not list(tmp_path.rglob("*.extract.part"))


def test_zalo_missing_kaggle_credentials_skips_without_metadata_requests() -> None:
    client = ZaloClient()
    client.kaggle_auth = None
    with pytest.raises(core.SkipDataset):
        images._prepare_zalo_zip(zalo_dataset(), client, "small")
    assert not client.calls and not client.downloaded


@pytest.mark.parametrize("member", ["../outside.bin", "..\\outside.bin", "/absolute.bin"])
@pytest.mark.parametrize("selected_only", [False, True])
def test_safe_zip_rejects_path_traversal(tmp_path: Path, member: str, selected_only: bool) -> None:
    archive = tmp_path / "malicious.zip"
    archive.write_bytes(zip_bytes({"safe.txt": b"safe", member: b"escape"}))
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest, members=["safe.txt"] if selected_only else None)
    assert not (tmp_path / "outside.bin").exists()
    assert not (dest / "safe.txt").exists()


@pytest.mark.parametrize("selected_only", [False, True])
def test_safe_zip_rejects_symlink_before_extracting_regular_files(
    tmp_path: Path, selected_only: bool
) -> None:
    archive = tmp_path / "symlink.zip"
    link = zipfile.ZipInfo("link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as source:
        source.writestr("safe.txt", b"safe")
        source.writestr(link, "../outside.bin")
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest, members=["safe.txt"] if selected_only else None)
    assert not (dest / "safe.txt").exists()
    assert not (dest / "link").exists()


def test_safe_zip_selected_members_preserve_exact_original_bytes(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    archive.write_bytes(zip_bytes({**TRAIN, **IGNORED}))
    dest = tmp_path / "output"
    core.safe_extract_zip(archive, dest, members=list(TRAIN))
    assert {
        str(path.relative_to(dest).as_posix()) for path in dest.rglob("*") if path.is_file()
    } == set(TRAIN)
    for member, contents in TRAIN.items():
        assert (dest / member).read_bytes() == contents


def mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> core.Client:
    client = core.Client()
    client._http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return client


def remote_fixture() -> core.RemoteFile:
    return core.RemoteFile(
        "https://example.test/archive.zip", "archive.zip", 6, hashlib.sha256(b"abcdef").hexdigest()
    )


def partial_fixture(dest: Path, payload: bytes, remote: core.RemoteFile) -> None:
    dest.with_name(dest.name + ".part").write_bytes(payload)
    resource = hashlib.sha256(
        (remote.url + str(remote.size) + str(remote.sha256)).encode()
    ).hexdigest()
    dest.with_name(dest.name + ".part.json").write_text(
        json.dumps({"resource": resource}), encoding="utf-8"
    )


def test_http_416_discards_stale_partial_and_retries_once_without_range(tmp_path: Path) -> None:
    remote = remote_fixture()
    dest = tmp_path / remote.path
    partial_fixture(dest, b"abc", remote)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert len(requests) <= 2, "416 recovery must not loop"
        if len(requests) == 1:
            assert request.headers["range"] == "bytes=3-"
            return httpx.Response(416, headers={"Content-Range": "bytes */6"})
        assert "range" not in request.headers
        return httpx.Response(200, content=b"abcdef")

    client = mock_client(handler)
    client.download(remote, dest)
    assert len(requests) == 2
    assert dest.read_bytes() == b"abcdef"
    assert not dest.with_name(dest.name + ".part").exists()
    assert not dest.with_name(dest.name + ".part.json").exists()


def test_oversized_partial_is_reset_before_any_range_request(tmp_path: Path) -> None:
    remote = remote_fixture()
    dest = tmp_path / remote.path
    partial_fixture(dest, b"too-long-partial", remote)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert "range" not in request.headers
        return httpx.Response(200, content=b"abcdef")

    client = mock_client(handler)
    client.download(remote, dest)
    assert len(requests) == 1
    assert dest.read_bytes() == b"abcdef"
    assert not dest.with_name(dest.name + ".part").exists()


@pytest.mark.parametrize("has_partial", [False, True])
def test_persistent_416_is_bounded_and_leaves_no_stale_partial(
    tmp_path: Path, has_partial: bool
) -> None:
    remote = remote_fixture()
    dest = tmp_path / remote.path
    if has_partial:
        partial_fixture(dest, b"abc", remote)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert len(requests) <= 6, "persistent 416 must fail with bounded attempts"
        if len(requests) > 1:
            assert "range" not in request.headers
        return httpx.Response(416, headers={"Content-Range": "bytes */6"})

    client = mock_client(handler)
    with pytest.raises(core.DownloadError):
        client.download(remote, dest)
    assert 1 <= len(requests) <= 6
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_safe_zip_reextracts_same_size_corrupted_output_using_crc(tmp_path: Path) -> None:
    member = "train/train/videos/first.mp4"
    original = TRAIN[member]
    archive = tmp_path / "source.zip"
    archive.write_bytes(zip_bytes({member: original}))
    dest = tmp_path / "output"
    target = dest / member
    target.parent.mkdir(parents=True)
    target.write_bytes(b"X" * len(original))
    assert target.stat().st_size == len(original)
    assert target.read_bytes() != original
    core.safe_extract_zip(archive, dest, members=[member])
    assert target.read_bytes() == original
    assert not target.with_name(target.name + ".extract.part").exists()


def test_safe_zip_rejects_symlink_at_partial_extraction_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "source.zip"
    archive.write_bytes(zip_bytes({"video.mp4": b"original-video"}))
    dest = tmp_path / "output"
    dest.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"must-stay-unchanged")
    partial = dest / "video.mp4.extract.part"
    try:
        partial.symlink_to(outside)
    except OSError:
        # Windows can deny symlink creation; still exercise the link guard offline.
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            Path, "is_symlink", lambda path: path == partial or original_is_symlink(path)
        )
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert outside.read_bytes() == b"must-stay-unchanged"
    assert not (dest / "video.mp4").exists()


def test_zalo_missing_labelled_video_fails_before_extracting_any_train_file(tmp_path: Path) -> None:
    client = ZaloClient()
    client.payload = zip_bytes(
        {
            path: payload
            for path, payload in {**TRAIN, **IGNORED}.items()
            if not path.endswith("second.mp4")
        }
    )
    plan = images._prepare_zalo_zip(zalo_dataset(), client, "small")
    assert plan.execute is not None
    with pytest.raises(core.DownloadError):
        plan.execute(tmp_path, client)
    assert len(client.downloaded) == 1
    assert all(not (tmp_path / path).exists() for path in TRAIN)
    assert not (tmp_path / "selected_manifest.json").exists()


def test_zalo_small_budget_must_cover_archive_and_extracted_train() -> None:
    client = ZaloClient()
    train_bytes = sum(
        len(payload)
        for path, payload in {**TRAIN, **IGNORED}.items()
        if path == LABEL_PATH or path.startswith("train/train/videos/")
    )
    budget = len(client.payload) + train_bytes - 1
    assert budget > len(client.payload), "archive fits but extraction must not be forgotten"
    with pytest.raises(core.SkipDataset):
        images._prepare_zalo_zip(zalo_dataset(budget), client, "small")
    assert not client.downloaded


def test_catalog_fits_real_zalo_peak_and_preserves_room_for_existing_vimd_subset() -> None:
    """Measured ZIP and selected-train bytes must fit before any actual media transfer."""
    import download_data as main

    # Kaggle whole ZIP metadata verified on 2026-10-17; these are distinct from
    # the older totalBytes figure that omitted ZIP container/compression costs.
    zip_size = 2_814_863_037
    train_size = 1_965_509_735
    existing_vimd_bytes = 62_853_393  # 19 clips, all clips for the same 12 selected people.

    class MeasuredMetadataClient(ZaloClient):
        def head_size(self, url: str, **kwargs: object) -> int:
            assert "datasetVersionNumber=7" in url
            return zip_size

        def json(self, url: str, **kwargs: object) -> dict:
            if "/view/" in url:
                return {"currentVersionNumber": 7, "totalBytes": train_size}
            assert "/list/" in url
            return {
                "datasetFiles": [
                    {"name": LABEL_PATH, "totalBytes": len(LABEL_BYTES)},
                    {
                        "name": "train/train/videos/first.mp4",
                        "totalBytes": train_size - len(LABEL_BYTES),
                    },
                ]
            }

    dataset = main.DATASETS["zalo2022"]
    # Main reserves up to 5 MB before provider preparation and adds at least
    # 1 MB afterward for SOURCE/manifest bookkeeping.
    provider = replace(
        dataset, budget_bytes=dataset.budget_bytes - min(5_000_000, dataset.budget_bytes // 100)
    )
    client = MeasuredMetadataClient()
    plan = images._prepare_zalo_zip(provider, client, "small")
    assert plan.peak_bytes == zip_size + train_size
    assert plan.peak_bytes + 1_000_000 <= dataset.budget_bytes
    assert sum(item.budget_bytes for item in main.DATASETS.values()) < 30_000_000_000
    vimd = main.DATASETS["vimd"]
    assert (
        vimd.budget_bytes - min(5_000_000, vimd.budget_bytes // 100)
        >= existing_vimd_bytes + 10_000_000
    )
    assert not client.downloaded
