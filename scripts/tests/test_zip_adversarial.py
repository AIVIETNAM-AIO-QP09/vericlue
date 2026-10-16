"""Adversarial offline ZIP tests: boundaries, caps, cleanup, and sanitized errors."""

from __future__ import annotations

import io
import json
import stat
import struct
import sys
import warnings
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import data_download_core as core  # noqa: E402
import data_download_images as images  # noqa: E402


def snapshot(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in folder.rglob("*")
        if path.is_file()
    }


@pytest.fixture(autouse=True)
def outside_guard(tmp_path: Path) -> Iterator[None]:
    """Every case proves its outside sentinel and outside inventory stay untouched."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel.bin").write_bytes(b"outside-must-not-change")
    before = snapshot(outside)
    yield
    assert snapshot(outside) == before


def archive_bytes(
    entries: list[tuple[str | zipfile.ZipInfo, bytes]], *, compression: int = zipfile.ZIP_DEFLATED
) -> bytes:
    buffer = io.BytesIO()
    # Intentional duplicate-name fixtures must remain quiet in test output.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate name:", category=UserWarning)
        with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
            for name, payload in entries:
                archive.writestr(name, payload)
    return buffer.getvalue()


def write_archive(tmp_path: Path, payload: bytes) -> Path:
    path = tmp_path / "source.zip"
    path.write_bytes(payload)
    return path


def assert_no_partials(dest: Path) -> None:
    assert not list(dest.rglob("*.extract.part"))


@pytest.mark.parametrize("member", ["C:x", "C:" + chr(92) + "x", "../outside/sentinel.bin"])
def test_drive_and_traversal_names_fail_before_any_output(tmp_path: Path, member: str) -> None:
    archive = write_archive(tmp_path, archive_bytes([("safe.bin", b"safe"), (member, b"attack")]))
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert snapshot(dest) == {}
    assert_no_partials(dest)


@pytest.mark.parametrize(
    "first,second",
    [("same.bin", "same.bin"), ("Case.bin", "case.bin"), ("a" + chr(92) + "b.bin", "a/b.bin")],
)
def test_duplicate_normalized_zip_paths_fail_before_any_output(
    tmp_path: Path, first: str, second: str
) -> None:
    archive = write_archive(
        tmp_path, archive_bytes([("00-safe.bin", b"safe"), (first, b"first"), (second, b"second")])
    )
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert snapshot(dest) == {}
    assert_no_partials(dest)


def test_encryption_flags_in_local_and_central_headers_are_rejected(tmp_path: Path) -> None:
    payload = bytearray(archive_bytes([("payload.bin", b"plain-fixture")]))
    for signature, offset in (("504b0304", 6), ("504b0102", 8)):
        position = payload.find(bytes.fromhex(signature))
        assert position >= 0
        flags = struct.unpack_from("<H", payload, position + offset)[0]
        struct.pack_into("<H", payload, position + offset, flags | 1)
    archive = write_archive(tmp_path, bytes(payload))
    with zipfile.ZipFile(archive) as source:
        assert source.infolist()[0].flag_bits & 1
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert snapshot(dest) == {}
    assert_no_partials(dest)


def test_windows_reparse_point_attribute_is_rejected(tmp_path: Path) -> None:
    entry = zipfile.ZipInfo("reparse.bin")
    entry.create_system = 0
    entry.external_attr = 0x400 | ((stat.S_IFREG | 0o644) << 16)
    archive = write_archive(tmp_path, archive_bytes([("00-safe.bin", b"safe"), (entry, b"target")]))
    with zipfile.ZipFile(archive) as source:
        assert source.getinfo("reparse.bin").external_attr & 0x400
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert snapshot(dest) == {}
    assert_no_partials(dest)


@pytest.mark.parametrize("kind", ["not-a-zip", "truncated-directory"])
def test_malformed_zip_is_sanitized_without_partial_output(tmp_path: Path, kind: str) -> None:
    valid = archive_bytes([("payload.bin", b"fixture")])
    archive = write_archive(tmp_path, b"not a ZIP" if kind == "not-a-zip" else valid[:-22])
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert snapshot(dest) == {}
    assert_no_partials(dest)


def test_corrupt_stored_payload_crc_removes_partial_output(tmp_path: Path) -> None:
    payload = bytearray(
        archive_bytes([("payload.bin", b"original-payload")], compression=zipfile.ZIP_STORED)
    )
    local = payload.find(bytes.fromhex("504b0304"))
    name_length, extra_length = struct.unpack_from("<HH", payload, local + 26)
    data_offset = local + 30 + name_length + extra_length
    payload[data_offset] ^= 0xFF
    archive = write_archive(tmp_path, bytes(payload))
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert not (dest / "payload.bin").exists()
    assert_no_partials(dest)


@pytest.mark.parametrize("error_type", [zlib.error, NotImplementedError])
def test_decompression_failure_is_sanitized_and_cleans_partial_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    archive = write_archive(tmp_path, archive_bytes([("payload.bin", b"original-payload")]))
    secret = "signed-url-secret-must-not-leak"
    calls = 0

    def failing_read(stream: zipfile.ZipExtFile, size: int = -1) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            return b"abc"
        raise error_type(secret)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", failing_read)
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError) as caught:
        core.safe_extract_zip(archive, dest)
    assert secret not in str(caught.value)
    assert not (dest / "payload.bin").exists()
    assert_no_partials(dest)


@pytest.mark.parametrize("already_exists", [False, True])
def test_zip_bomb_cap_counts_selected_uncompressed_bytes_even_when_already_present(
    tmp_path: Path, already_exists: bool
) -> None:
    expanded = b"A" * 100_000
    archive = write_archive(tmp_path, archive_bytes([("bomb.bin", expanded)]))
    assert archive.stat().st_size < 1_024
    dest = tmp_path / "output"
    if already_exists:
        dest.mkdir()
        (dest / "bomb.bin").write_bytes(expanded)
    before = snapshot(dest)
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest, max_total_bytes=1_024)
    assert snapshot(dest) == before
    assert_no_partials(dest)


def test_cap_counts_selected_members_instead_of_unselected_regular_payloads(tmp_path: Path) -> None:
    archive = write_archive(
        tmp_path, archive_bytes([("small.bin", b"ok"), ("large.bin", b"A" * 100_000)])
    )
    dest = tmp_path / "output"
    core.safe_extract_zip(archive, dest, members=["small.bin"], max_total_bytes=2)
    assert snapshot(dest) == {"small.bin": b"ok"}
    assert_no_partials(dest)


def test_streamed_bytes_over_cap_stop_before_a_second_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = write_archive(tmp_path, archive_bytes([("payload.bin", b"abc")]))
    calls = 0

    def oversized_read(stream: zipfile.ZipExtFile, size: int = -1) -> bytes:
        nonlocal calls
        calls += 1
        assert calls == 1, "must stop immediately once actual uncompressed bytes exceed cap"
        return b"abcd"

    monkeypatch.setattr(zipfile.ZipExtFile, "read", oversized_read)
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest, max_total_bytes=3)
    assert calls == 1
    assert not (dest / "payload.bin").exists()
    assert_no_partials(dest)


@pytest.mark.parametrize("malformed", [False, True])
def test_stale_regular_extraction_partials_are_cleaned_at_start(
    tmp_path: Path, malformed: bool
) -> None:
    payload = b"invalid ZIP" if malformed else archive_bytes([("payload.bin", b"new-data")])
    archive = write_archive(tmp_path, payload)
    dest = tmp_path / "output"
    stale = dest / "old" / "unused.extract.part"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"interrupted")
    kept = dest / "keep.bin"
    kept.write_bytes(b"keep-existing-data")
    if malformed:
        with pytest.raises(core.DownloadError):
            core.safe_extract_zip(archive, dest)
    else:
        core.safe_extract_zip(archive, dest)
        assert (dest / "payload.bin").read_bytes() == b"new-data"
    assert not stale.exists()
    assert kept.read_bytes() == b"keep-existing-data"
    assert_no_partials(dest)


def test_partial_symlink_is_rejected_instead_of_cleaned_or_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = write_archive(tmp_path, archive_bytes([("payload.bin", b"new-data")]))
    dest = tmp_path / "output"
    dest.mkdir()
    partial = dest / "payload.bin.extract.part"
    other_stale = dest / "earlier.extract.part"
    other_stale.write_bytes(b"validate-all-links-before-deleting-anything")
    outside = tmp_path / "outside" / "sentinel.bin"
    try:
        partial.symlink_to(outside)
    except OSError:
        partial.write_bytes(b"placeholder-for-link-guard")
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == partial or original(path))
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert partial.exists()
    assert other_stale.read_bytes() == b"validate-all-links-before-deleting-anything"
    assert not (dest / "payload.bin").exists()


@pytest.mark.parametrize("declared_delta", [-1, 1])
def test_zalo_inventory_size_mismatch_fails_before_extracting_train(
    tmp_path: Path, declared_delta: int
) -> None:
    label_path = "train/train/label.csv"
    video_path = "train/train/videos/clip.mp4"
    labels = b"fname,liveness_score\nclip.mp4,0\n"
    video = b"original-video"
    payload = archive_bytes([(label_path, labels), (video_path, video)])

    class FakeClient:
        kaggle_auth = ("fixture", "dummy-key")

        def json(self, url: str, **kwargs: object) -> dict:
            if "/view/" in url:
                return {"currentVersionNumber": 7}
            assert "/list/" in url
            return {
                "datasetFiles": [
                    {"name": label_path, "totalBytes": len(labels)},
                    {"name": video_path, "totalBytes": len(video) + declared_delta},
                ]
            }

        def head_size(self, url: str) -> int:
            return len(payload)

        def download(self, remote: core.RemoteFile, dest: Path) -> None:
            assert remote.size == len(payload)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)

    dataset = core.Dataset("zalo2022", "https://example.test/zalo", "fixture", None, 1_000_000)
    client = FakeClient()
    plan = images._prepare_zalo_zip(dataset, client, "small")
    dest = tmp_path / "output"
    assert plan.execute is not None
    with pytest.raises(core.DownloadError):
        plan.execute(dest, client)
    assert not (dest / label_path).exists()
    assert not (dest / video_path).exists()
    assert not (dest / "selected_manifest.json").exists()
    assert_no_partials(dest)


@pytest.mark.parametrize("member", ["CON", "nested/NUL.txt", "trailing.", "trailing "])
def test_safe_path_rejects_reserved_windows_names_and_trailing_aliases(
    tmp_path: Path, member: str
) -> None:
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_path(dest, member)
    assert not dest.exists()


def test_inventory_never_counts_extract_partials_from_index_or_manifest(tmp_path: Path) -> None:
    import download_data as main

    dest = tmp_path / "output"
    dest.mkdir()
    (dest / "index.csv").write_text(
        "path,source_video_id,subject_id,archive\n"
        "videos/good.mp4,good-video,known-person,good-archive\n"
        "videos/bad.mp4.extract.part,bad-video,bad-person,bad-archive\n",
        encoding="utf-8",
    )
    (dest / "selected_manifest.json").write_text(
        json.dumps(
            [
                {
                    "path": "videos/good.mp4",
                    "size": 7,
                    "subject_id": "known-person",
                    "region": "North",
                },
                {
                    "path": "videos/bad.mp4.extract.part",
                    "size": 999,
                    "subject_id": "bad-person",
                    "region": "South",
                },
            ]
        ),
        encoding="utf-8",
    )
    result = main.data_inventory(dest)
    assert "inventory_error" not in result
    assert result["index_rows"] == 1
    assert result["source_videos"] == 1
    assert result["indexed_archives"] == 1
    assert result["selected_files"] == 1
    assert result["manifest_data_bytes"] == 7
    assert result["known_subjects"] == 1
    assert result["regions"] == {"North": {"files": 1, "subjects": 1}}


@pytest.mark.parametrize("ancestor", ["a", "A"])
def test_regular_file_cannot_be_an_ancestor_of_another_zip_member(
    tmp_path: Path, ancestor: str
) -> None:
    archive = write_archive(
        tmp_path,
        archive_bytes(
            [
                ("00-safe.bin", b"must-not-be-written"),
                (ancestor, b"regular-file"),
                ("a/b.bin", b"nested-file"),
            ]
        ),
    )
    dest = tmp_path / "output"
    with pytest.raises(core.DownloadError):
        core.safe_extract_zip(archive, dest)
    assert snapshot(dest) == {}
    assert_no_partials(dest)
