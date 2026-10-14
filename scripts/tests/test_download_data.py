"""Offline coverage for dataset downloads and provenance safety."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import shutil
import sys
import tarfile
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import data_download_core as core  # noqa: E402


def load_main():
    spec = importlib.util.spec_from_file_location(
        "download_data", ROOT / "scripts/download_data.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_client(handler):
    client = core.Client()
    client._http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    return client


def create_partial(dest, data, file):
    Path(str(dest) + ".part").write_bytes(data)
    resource = hashlib.sha256((file.url + str(file.size) + str(file.sha256)).encode()).hexdigest()
    Path(str(dest) + ".part.json").write_text(json.dumps({"resource": resource}), encoding="utf-8")


def test_sample_groups_is_stable_and_keeps_complete_original_video_pairs():
    groups = {
        f"person-{i}": [
            core.RemoteFile("https://example.test/real", f"{i}/real.mp4", 3),
            core.RemoteFile("https://example.test/fake", f"{i}/fake.mp4", 3),
        ]
        for i in range(12)
    }
    names, files = core.sample_groups(groups, 19, 2026)
    again = core.sample_groups(dict(reversed(list(groups.items()))), 19, 2026)
    assert (names, files) == again
    assert names
    assert sum(file.size for file in files) <= 19
    assert files == [file for name in names for file in groups[name]]
    assert all(
        len([file for file in files if str(file.path).startswith(name.split("-")[1] + "/")]) == 2
        for name in names
    )


def test_group_larger_than_budget_is_never_truncated():
    groups = {
        "whole-person": [
            core.RemoteFile("https://example.test/a", "a", 4),
            core.RemoteFile("https://example.test/b", "b", 4),
        ]
    }
    assert core.sample_groups(groups, 7, 2026) == ([], [])


def test_disk_check_reserves_ten_gb_and_uses_existing_ancestor(tmp_path, monkeypatch):
    checked = []

    def usage(path):
        checked.append(Path(path))
        return shutil._ntuple_diskusage(100_000_000_000, 0, 13_000_000_000)

    monkeypatch.setattr(core.shutil, "disk_usage", usage)
    missing = tmp_path / "new" / "raw"
    core.check_disk(missing, 3_000_000_000)
    assert checked == [tmp_path]
    with pytest.raises(core.DownloadError):
        core.check_disk(missing, 3_000_000_001)
    assert not missing.exists()


def test_disk_check_accounts_for_archive_and_extracted_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(20_000_000_000, 0, 12_000_000_000),
    )
    # A 1 GB archive needs another 2 GB for extraction: reserving only its
    # download size would incorrectly allow this operation.
    with pytest.raises(core.DownloadError):
        core.check_disk(tmp_path, 1_000_000_000 + 2_000_000_000)


def test_download_skips_complete_file_without_network(tmp_path):
    data = b"complete data"
    dest = tmp_path / "sample.bin"
    dest.write_bytes(data)

    def unexpected(_):
        pytest.fail("complete file must not request network")

    client = make_client(unexpected)
    client.download(
        core.RemoteFile(
            "https://example.test/sample", "sample.bin", len(data), hashlib.sha256(data).hexdigest()
        ),
        dest,
    )
    assert dest.read_bytes() == data


def test_resume_requests_exact_range_and_accepts_206(tmp_path):
    dest = tmp_path / "sample.bin"
    partial = Path(str(dest) + ".part")
    file = core.RemoteFile(
        "https://example.test/sample", "sample.bin", 6, hashlib.sha256(b"abcdef").hexdigest()
    )
    create_partial(dest, b"abc", file)
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["range"] == "bytes=3-"
        assert not dest.exists()
        return httpx.Response(
            206, headers={"Content-Range": "bytes 3-5/6", "Content-Length": "3"}, content=b"def"
        )

    client = make_client(handler)
    client.download(
        core.RemoteFile(
            "https://example.test/sample", "sample.bin", 6, hashlib.sha256(b"abcdef").hexdigest()
        ),
        dest,
    )
    assert len(requests) == 1
    assert dest.read_bytes() == b"abcdef"
    assert not partial.exists()


def test_server_ignoring_range_restarts_instead_of_appending(tmp_path):
    dest = tmp_path / "sample.bin"
    file = core.RemoteFile("https://example.test/sample", "sample.bin", 6)
    create_partial(dest, b"abc", file)
    client = make_client(
        lambda _: httpx.Response(200, headers={"Content-Length": "6"}, content=b"abcdef")
    )
    client.download(core.RemoteFile("https://example.test/sample", "sample.bin", 6), dest)
    assert dest.read_bytes() == b"abcdef"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(206, headers={"Content-Range": "bytes 2-5/6"}, content=b"cdef"),
        httpx.Response(206, headers={"Content-Range": "bytes 3-5/7"}, content=b"def"),
        httpx.Response(206, content=b"def"),
    ],
)
def test_resume_rejects_inconsistent_content_range(tmp_path, response):
    dest = tmp_path / "sample.bin"
    file = core.RemoteFile("https://example.test/sample", "sample.bin", 6)
    create_partial(dest, b"abc", file)
    client = make_client(lambda _: response)
    with pytest.raises(core.DownloadError):
        client.download(core.RemoteFile("https://example.test/sample", "sample.bin", 6), dest)
    assert not dest.exists()


@pytest.mark.parametrize("body, expected_hash", [(b"short", None), (b"abcdef", "0" * 64)])
def test_invalid_size_or_hash_never_replaces_destination(tmp_path, body, expected_hash):
    dest = tmp_path / "sample.bin"
    client = make_client(lambda _: httpx.Response(200, content=body))
    with pytest.raises(core.DownloadError):
        client.download(
            core.RemoteFile("https://example.test/sample", "sample.bin", 6, expected_hash), dest
        )
    assert not dest.exists()


def make_tar(path, entries):
    with tarfile.open(path, "w") as archive:
        for name, body in entries:
            member = tarfile.TarInfo(name)
            member.size = len(body)
            archive.addfile(member, io.BytesIO(body))


@pytest.mark.parametrize("name", ["../escape.txt", "/absolute.txt", "person/../../escape.txt"])
def test_archive_traversal_is_rejected(tmp_path, name):
    archive = tmp_path / "source.tar"
    make_tar(archive, [(name, b"bad")])
    with pytest.raises(core.DownloadError):
        core.safe_extract_tar(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_archive_symlink_escape_is_rejected(tmp_path):
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as handle:
        member = tarfile.TarInfo("person/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../escape.txt"
        handle.addfile(member)
    with pytest.raises(core.DownloadError):
        core.safe_extract_tar(archive, tmp_path / "out")


def test_archive_can_extract_whole_selected_group(tmp_path):
    archive = tmp_path / "source.tar"
    make_tar(
        archive,
        [
            ("person-a/real.wav", b"real"),
            ("person-a/fake.wav", b"fake"),
            ("person-b/real.wav", b"other"),
        ],
    )
    dest = tmp_path / "out"
    core.safe_extract_tar(archive, dest, members=["person-a/real.wav", "person-a/fake.wav"])
    assert (dest / "person-a/real.wav").read_bytes() == b"real"
    assert (dest / "person-a/fake.wav").read_bytes() == b"fake"
    assert not (dest / "person-b/real.wav").exists()


def test_source_records_license_seed_groups_and_file_inventory(tmp_path):
    dataset = core.Dataset(
        "example", "https://example.test/data", "giấy phép chưa rõ — không phân phối lại", 20, 10
    )
    files = [core.RemoteFile("https://example.test/a", "person-a/real.wav", 4)]
    plan = core.Plan(dataset, files, 8, revision="pinned-revision", groups=["person-a"])
    (tmp_path / "person-a").mkdir()
    (tmp_path / "person-a/real.wav").write_bytes(b"real")
    path = core.write_source(plan, tmp_path, seed=2026, status="downloaded")
    text = path.read_text(encoding="utf-8")
    for expected in [
        dataset.source,
        dataset.license,
        "2026",
        "person-a",
        "person-a/real.wav",
        "pinned-revision",
    ]:
        assert expected in text
    assert path.name == "SOURCE.md"


def test_data_dir_env_and_relative_default(monkeypatch, tmp_path):
    module = load_main()
    monkeypatch.delenv("DATA_DIR", raising=False)
    assert module.resolve_data_dir() == ROOT / "data"
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "shared-data"))
    assert module.resolve_data_dir() == tmp_path / "shared-data"
    assert module.resolve_data_dir("alternate") == ROOT / "alternate"


def configure_main(monkeypatch, tmp_path, *, gated=False):
    module = load_main()
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path / "no-credentials"))
    dataset = core.Dataset(
        "example", "https://example.test/data", "CC BY 4.0", 100, 10, gated=gated
    )
    monkeypatch.setattr(module, "DATASETS", {"example": dataset})
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "new-data"))
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(100_000_000_000, 0, 100_000_000_000),
    )
    return module, dataset


def test_dry_run_prints_plan_but_does_not_create_or_download(tmp_path, monkeypatch, capsys):
    module, dataset = configure_main(monkeypatch, tmp_path)
    planned = []

    def prepare(selected, client, seed, subset):
        planned.append((selected.name, subset))
        return core.Plan(dataset, [core.RemoteFile("https://example.test/a", "a.wav", 10)], 20)

    monkeypatch.setattr(module, "prepare_dataset", prepare)
    monkeypatch.setattr(
        core.Client, "download", lambda *args: pytest.fail("dry-run must not download")
    )
    assert module.main(["--only", "example", "--dry-run"]) == 0
    assert planned == []
    assert "small" in capsys.readouterr().out
    assert not (tmp_path / "new-data").exists()


def test_missing_gated_token_skips_before_network_and_explains_token(tmp_path, monkeypatch, capsys):
    module, _ = configure_main(monkeypatch, tmp_path, gated=True)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(
        module,
        "prepare_dataset",
        lambda *args: pytest.fail("missing token must not contact gated provider"),
    )
    assert module.main(["--only", "example"]) != 0
    assert "HF_TOKEN" in capsys.readouterr().out


def test_failure_keeps_other_sources_running_and_redacts_credentials(tmp_path, monkeypatch, capsys):
    module, dataset = configure_main(monkeypatch, tmp_path)
    other = core.Dataset("other", "https://example.test/other", "MIT", 4, 4)
    monkeypatch.setattr(module, "DATASETS", {"example": dataset, "other": other})
    secret = "hf_private_token_never_print"
    monkeypatch.setenv("HF_TOKEN", secret)
    monkeypatch.setenv("KAGGLE_USERNAME", "test-user")
    monkeypatch.setenv("KAGGLE_KEY", "kaggle_private_key_never_print")
    visited = []

    def prepare(selected, client, seed, subset):
        visited.append(selected.name)
        if selected.name == "example":
            raise core.DownloadError(f"provider rejected token {secret}")
        return core.Plan(other, [], 0, execute=lambda dest, client: None)

    monkeypatch.setattr(module, "prepare_dataset", prepare)
    assert module.main(["--only", "example", "other"]) != 0
    assert visited == ["example", "other"]
    output = capsys.readouterr()
    assert secret not in output.out + output.err
    assert "kaggle_private_key_never_print" not in output.out + output.err
    for source in (tmp_path / "new-data").rglob("SOURCE.md"):
        assert secret not in source.read_text(encoding="utf-8")


def test_mlaad_filters_vietnamese_and_keeps_source_sentence_across_tts():
    import data_download_audio as audio

    metadata = {
        "fake/vi/model-a/meta.csv": b"path|original_file|reference_speaker\na.wav|sentence-1|speaker-1\n",
        "fake/vi/model-b/meta.csv": b"path|original_file|reference_speaker\nb.wav|sentence-1|speaker-1\n",
    }
    entries = [
        {"path": "fake/vi/model-a/a.wav", "size": 4, "type": "file"},
        {"path": "fake/vi/model-b/b.wav", "size": 4, "type": "file"},
        {"path": "fake/en/model-a/ignore.wav", "size": 4, "type": "file"},
    ] + [{"path": path, "size": len(payload), "type": "file"} for path, payload in metadata.items()]

    class FakeClient:
        token = ""

        def hf_files(self, repo, prefix=""):
            return "revision", entries

        def get_bytes(self, url, **kwargs):
            return next(payload for path, payload in metadata.items() if url.endswith(path))

    dataset = core.Dataset(
        "mlaad_vi", "https://example.test", "CC BY NC 4.0", 100_000_000, 100_000_000
    )
    plan = audio.prepare(dataset, FakeClient(), 2026, "small")
    assert plan.groups == ["sentence-1"]
    assert sorted(file.path for file in plan.files) == [
        "fake/vi/model-a/a.wav",
        "fake/vi/model-b/b.wav",
    ]
    dataset = core.Dataset("mlaad_vi", "https://example.test", "CC BY NC 4.0", 1000, 7)
    with pytest.raises(core.SkipDataset):
        audio.prepare(dataset, FakeClient(), 2026, "small")


def test_vivos_extracts_complete_speakers_and_records_manifest(tmp_path, monkeypatch):
    import json

    import data_download_audio as audio

    archive = tmp_path / "vivos.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        for name, content in [
            ("vivos/train/waves/A/a.wav", b"aa"),
            ("vivos/train/waves/A/b.wav", b"bb"),
            ("vivos/test/waves/B/c.wav", b"cc"),
        ]:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            handle.addfile(member, io.BytesIO(content))
    payload = archive.read_bytes()

    class FakeClient:
        token = ""

        def hf_files(self, repo, prefix=""):
            return "revision", [{"path": "data/vivos.tar.gz", "size": len(payload), "type": "file"}]

        def download(self, remote, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)

    monkeypatch.setattr(
        audio.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(100_000_000_000, 0, 100_000_000_000),
    )
    dataset = core.Dataset("vivos", "https://example.test", "CC BY SA 4.0", 1000, 100)
    plan = audio.prepare(dataset, FakeClient(), 2026, "small")
    dest = tmp_path / "outputs"
    dest.mkdir()
    plan.execute(dest, FakeClient())
    rows = json.loads((dest / "selected_manifest.json").read_text(encoding="utf-8"))
    assert set(plan.groups) == {"A", "B"}
    assert {row["path"] for row in rows} == {
        "vivos/train/waves/A/a.wav",
        "vivos/train/waves/A/b.wav",
        "vivos/test/waves/B/c.wav",
    }
    assert sum(row["subject_id"] == "A" for row in rows) == 2
    assert plan.peak_bytes >= len(payload) + 250_000_000


def test_http_range_file_reads_exact_bytes_and_rejects_full_response():
    requests = []

    def handler(request):
        requests.append(request.headers["range"])
        return httpx.Response(206, headers={"Content-Range": "bytes 2-4/6"}, content=b"cde")

    client = make_client(handler)
    with client.remote_file("https://example.test/sample", 6) as source:
        source.seek(2)
        assert source.read(3) == b"cde"
        assert source.tell() == 5
    assert requests == ["bytes=2-4"]
    client = make_client(lambda _: httpx.Response(200, content=b"abcdef"))
    with (
        client.remote_file("https://example.test/sample", 6) as source,
        pytest.raises(core.SkipDataset),
    ):
        source.read(3)


def test_credentials_are_scoped_to_provider_and_http_error_hides_signed_url():
    client = core.Client(token="hf-secret", kaggle_auth=("user", "kaggle-secret"))
    assert (
        client._kwargs("https://huggingface.co/api")["headers"]["Authorization"]
        == "Bearer hf-secret"
    )
    assert "Authorization" not in client._kwargs("https://elsewhere.test/media")["headers"]
    assert "auth" not in client._kwargs("https://elsewhere.test/media")
    assert client._kwargs("https://www.kaggle.com/api")["auth"] == ("user", "kaggle-secret")

    def interrupted(request):
        raise httpx.ReadError("signed URL secret-query", request=request)

    client._http = httpx.Client(transport=httpx.MockTransport(interrupted))
    with pytest.raises(core.DownloadError) as error:
        client.get_bytes("https://example.test/file?token=secret-query")
    assert "secret-query" not in str(error.value)


def test_range_server_ignoring_range_is_rejected_before_reading_large_body():
    class ForbiddenBody(httpx.SyncByteStream):
        def __iter__(self):
            pytest.fail("Range fallback must never consume the full response")
            yield b""

    client = make_client(lambda _: httpx.Response(200, stream=ForbiddenBody()))
    with (
        client.remote_file("https://example.test/large", 1_000_000_000) as source,
        pytest.raises(core.SkipDataset),
    ):
        source.read(100)


@pytest.mark.parametrize("subset", ["small", "full"])
def test_main_preflight_stops_before_provider_when_reserve_not_available(
    tmp_path, monkeypatch, subset
):
    module, _ = configure_main(monkeypatch, tmp_path)
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(20_000_000_000, 0, 10_000_000_000),
    )
    monkeypatch.setattr(
        module,
        "prepare_dataset",
        lambda *args: pytest.fail("preflight must precede provider access"),
    )
    assert module.main(["--only", "example", "--subset", subset]) == 1
    assert not (tmp_path / "new-data").exists()


def test_kaggle_without_credentials_skips_and_explains_both_methods(tmp_path, monkeypatch, capsys):
    module, _ = configure_main(monkeypatch, tmp_path)
    dataset = core.Dataset(
        "zalo2022", "https://www.kaggle.com/datasets/example", "chưa rõ", 100, 10
    )
    monkeypatch.setattr(module, "DATASETS", {"zalo2022": dataset})
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    monkeypatch.setattr(
        module,
        "prepare_dataset",
        lambda *args: pytest.fail("missing Kaggle credentials must skip provider"),
    )
    assert module.main(["--only", "zalo2022"]) == 2
    text = capsys.readouterr().out
    assert "KAGGLE_USERNAME" in text and "KAGGLE_KEY" in text and "kaggle.json" in text


def test_kaggle_json_credentials_loaded_without_printing(tmp_path, monkeypatch, capsys):
    module = load_main()
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path))
    (tmp_path / "kaggle.json").write_text(
        json.dumps({"username": "private-user", "key": "private-key"})
    )
    _, credentials = module.load_credentials()
    assert credentials == ("private-user", "private-key")
    assert not capsys.readouterr().out


def test_tar_wrong_size_existing_file_requires_replacement_scratch(tmp_path, monkeypatch):
    archive = tmp_path / "source.tar"
    make_tar(archive, [("person/real.wav", b"replacement")])
    dest = tmp_path / "out"
    (dest / "person").mkdir(parents=True)
    existing = dest / "person/real.wav"
    existing.write_bytes(b"old")
    replacement_size = len(b"replacement")
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(
            20_000_000_000, 0, core.RESERVE_BYTES + replacement_size - 1
        ),
    )
    with pytest.raises(core.DownloadError):
        core.safe_extract_tar(archive, dest)
    assert existing.read_bytes() == b"old"
    assert not list(dest.rglob("*.extract.part"))


def test_vimd_compressed_audio_must_validate_all_outputs_before_writing(tmp_path, monkeypatch):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    import data_download_audio as audio

    # Compression makes all three complete speakers appear cheap in parquet,
    # while decoded audio cannot fit the declared disk/output allowance.
    table = pa.Table.from_pylist(
        [
            {
                "speakerID": f"speaker-{region}",
                "region": region,
                "audio": {"path": f"{region}.wav", "bytes": b"\0" * 5_000_000},
            }
            for region in ("North", "Central", "South")
        ]
    )
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="gzip", row_group_size=1)
    payload = buffer.getvalue()

    class FakeClient:
        token = ""

        def hf_files(self, repo, prefix=""):
            return "revision", [{"path": "train-000.parquet", "size": len(payload)}]

        def remote_file(self, url, size):
            return io.BytesIO(payload)

    monkeypatch.setattr(
        audio.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(100_000_000_000, 0, 100_000_000_000),
    )
    dataset = core.Dataset(
        "vimd", "https://example.test/vimd", "CC BY NC ND 4.0", len(payload), 10_500_000
    )
    plan = audio.prepare(dataset, FakeClient(), 2026, "small")
    assert set(plan.groups) == {"speaker-North", "speaker-Central", "speaker-South"}
    assert plan.peak_bytes < 15_000_000
    dest = tmp_path / "outputs"
    dest.mkdir()
    with pytest.raises(core.DownloadError):
        plan.execute(dest, FakeClient())
    assert not list(dest.rglob("*.wav"))
    assert not (dest / "selected_manifest.json").exists()


def test_vietnamese_celeb_source_lists_actual_identity_labels_after_download(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    import data_download_images as images

    buffer = io.BytesIO()
    pq.write_table(
        pa.table({"label": ["person-a", "person-a", "person-b"], "image": [b"a", b"b", b"c"]}),
        buffer,
    )
    payload = buffer.getvalue()

    class FakeClient:
        token = ""

        def hf_files(self, repo, prefix=""):
            return "revision", [{"path": "data/train.parquet", "size": len(payload)}]

        def download(self, remote, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)

    dataset = core.Dataset(
        "vn_celeb_faces",
        "https://example.test/celeb",
        "giấy phép chưa rõ",
        len(payload),
        100_000_000,
    )
    plan = images.prepare(dataset, FakeClient(), 2026, "small")
    if plan.execute:
        plan.execute(tmp_path, FakeClient())
    else:
        for file in plan.files:
            FakeClient().download(file, core.safe_path(tmp_path, file.path))
    source = core.write_source(plan, tmp_path, 2026, "complete").read_text(encoding="utf-8")
    assert set(plan.groups) == {"person-a", "person-b"}
    assert "person-a" in source and "person-b" in source


def test_rtfs_subset_preserves_real_and_every_fake_of_original_video():
    import data_download_images as images

    metadata = ["videos.csv", "photos.csv", "inswapper.csv", "uniface.csv"]
    inventory = [{"name": name, "totalBytes": 5} for name in metadata]
    originals = ["abcdefghijk", "ABCDEFGHIJK"]
    for source in originals:
        inventory.extend(
            {"name": path, "totalBytes": 4}
            for path in [
                f"original_videos/{source}_0_1.mp4",
                f"inswapper/inswapper_{source}_0_1.mp4",
                f"uniface/uniface_{source}_0_1.mp4",
            ]
        )

    class FakeClient:
        kaggle_auth = ("fixture", "fake-key")

        def json(self, url, **kwargs):
            return {"datasetFiles": inventory}

        def get_bytes(self, url, **kwargs):
            return b"id\n1\n"

    dataset = core.Dataset("rtfs10k", "https://example.test", "chưa rõ", 100, 32)
    plan = images.prepare(dataset, FakeClient(), 2026, "small")
    assert len(plan.groups) == 1
    source = plan.groups[0]
    assert {file.path for file in plan.files if file.path.endswith(".mp4")} == {
        f"original_videos/{source}_0_1.mp4",
        f"inswapper/inswapper_{source}_0_1.mp4",
        f"uniface/uniface_{source}_0_1.mp4",
    }
    assert {file.path for file in plan.files if file.path.endswith(".csv")} == set(metadata)
    assert plan.peak_bytes <= dataset.budget_bytes
    assert images.prepare(dataset, FakeClient(), 2026, "small").groups == plan.groups


def archive_bytes(entries, *, gzip=False):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:gz" if gzip else "w") as handle:
        for name, payload in entries:
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            handle.addfile(member, io.BytesIO(payload))
    return result.getvalue()


def test_wild_callback_downloads_archives_and_indexes_every_frame(tmp_path):
    import data_download_images as images

    payloads = {
        "data/fake_train/part.tar.gz": archive_bytes(
            [("video-a/000.jpg", b"a"), ("video-a/001.jpg", b"b")], gzip=True
        ),
        "data/real_train/part.tar.gz": archive_bytes(
            [("video-b/000.png", b"c"), ("video-b/001.png", b"d")], gzip=True
        ),
    }
    downloads = []

    class FakeClient:
        def hf_files(self, repo, prefix=""):
            return "revision", [
                {"path": path, "size": len(payload)} for path, payload in payloads.items()
            ]

        def download(self, remote, dest):
            downloads.append(remote.path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payloads[remote.path])

    dataset = core.Dataset("wilddeepfake", "https://example.test", "chưa rõ", 1_000_000, 5_000_000)
    plan = images.prepare(dataset, FakeClient(), 2026, "small")
    assert downloads == []
    plan.execute(tmp_path, FakeClient())
    assert set(downloads) == set(payloads)
    rows = [json.loads(line) for line in (tmp_path / "video_groups.jsonl").read_text().splitlines()]
    assert len(rows) == 4
    assert set(plan.groups) == {"fake_train::video-a", "real_train::video-b"}
    assert {row["member"] for row in rows} == {
        "video-a/000.jpg",
        "video-a/001.jpg",
        "video-b/000.png",
        "video-b/001.png",
    }
    assert {row["source_video_id"] for row in rows} == set(plan.groups)
    assert not list(tmp_path.rglob("*.jpg"))  # Keep full source archives, no frame copy.


def test_vicocktail_sample_id_maps_all_members_to_youtube_source(tmp_path):
    import data_download_images as images

    source = "abcdefghijk"
    members = [
        ("sample-0.sample_id", f"{source}_0_original".encode()),
        ("sample-0.wav", b"a"),
        ("sample-0.jpg", b"b"),
        ("sample-1.sample_id", f"{source}_1_original".encode()),
        ("sample-1.wav", b"c"),
    ]
    payload = archive_bytes(members)
    calls = []

    class FakeClient:
        def hf_files(self, repo, prefix=""):
            return "revision", [{"path": "data/avvn-train-000.tar", "size": len(payload)}]

        def download(self, remote, dest):
            calls.append(remote.path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)

    dataset = core.Dataset("vicocktail", "https://example.test", "chưa rõ", len(payload), 5_000_000)
    plan = images.prepare(dataset, FakeClient(), 2026, "small")
    assert calls == []
    plan.execute(tmp_path, FakeClient())
    assert calls == ["data/avvn-train-000.tar"]
    rows = [json.loads(line) for line in (tmp_path / "video_groups.jsonl").read_text().splitlines()]
    assert plan.groups == [source]
    assert len(rows) == 2
    assert {row["source_video_id"] for row in rows} == {source}
    assert {member for row in rows for member in row["members"]} == {name for name, _ in members}


def test_remaining_peak_credits_complete_and_valid_partial_but_keeps_scratch(tmp_path):
    dataset = core.Dataset("example", "https://example.test", "MIT", 200, 200)
    complete = core.RemoteFile("https://example.test/complete", "complete", 10)
    partial = core.RemoteFile("https://example.test/partial", "partial", 20)
    plan = core.Plan(dataset, [complete, partial], 100)
    (tmp_path / "complete").write_bytes(b"a" * 10)
    create_partial(tmp_path / "partial", b"b" * 8, partial)
    assert core.remaining_peak(plan, tmp_path) == 70 + 12
    Path(str(tmp_path / "partial") + ".part.json").write_text(
        json.dumps({"resource": "stale-other-source"})
    )
    assert core.remaining_peak(plan, tmp_path) == 70 + 20


def test_arbitrary_prepare_failure_continues_and_hides_exception_secrets(
    tmp_path, monkeypatch, capsys
):
    module, dataset = configure_main(monkeypatch, tmp_path)
    other = core.Dataset("other", "https://example.test/other", "MIT", 4, 4)
    monkeypatch.setattr(module, "DATASETS", {"example": dataset, "other": other})
    visited = []

    def prepare(selected, client, seed, subset):
        visited.append(selected.name)
        if selected.name == "example":
            raise RuntimeError("signed-url-unknown-secret-token")
        return core.Plan(other, [], 0, execute=lambda dest, client: None)

    monkeypatch.setattr(module, "prepare_dataset", prepare)
    assert module.main(["--only", "example", "other"]) == 1
    assert visited == ["example", "other"]
    captured = capsys.readouterr()
    assert "signed-url-unknown-secret-token" not in captured.out + captured.err
    for path in (tmp_path / "new-data").rglob("SOURCE.md"):
        assert "signed-url-unknown-secret-token" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["celeba_spoof", "lavdf"])
@pytest.mark.parametrize("subset", ["small", "full"])
def test_explicit_unsupported_image_sources_skip_without_provider_access(name, subset):
    import data_download_images as images

    class ForbiddenProvider:
        token = "fixture-token"

        def __getattr__(self, method):
            pytest.fail(f"unsupported source must not access provider: {method}")

    with pytest.raises(core.SkipDataset):
        images.prepare(
            core.Dataset(name, "https://example.test", "unknown", 100, 100),
            ForbiddenProvider(),
            2026,
            subset,
        )


@pytest.mark.parametrize("sidecar", ["verified", "partial"])
def test_corrupted_resume_json_restarts_download_safely(tmp_path, sidecar):
    dest = tmp_path / "audio.wav"
    if sidecar == "verified":
        dest.write_bytes(b"oldold")
        Path(str(dest) + ".verified.json").write_text("{not-json", encoding="utf-8")
    else:
        Path(str(dest) + ".part").write_bytes(b"old")
        Path(str(dest) + ".part.json").write_text("{not-json", encoding="utf-8")
    requests = []

    def handler(request):
        requests.append(request)
        assert "Range" not in request.headers
        return httpx.Response(200, content=b"abcdef")

    make_client(handler).download(
        core.RemoteFile("https://example.test/audio", "audio.wav", 6), dest
    )
    assert len(requests) == 1
    assert dest.read_bytes() == b"abcdef"
    assert (
        json.loads(Path(str(dest) + ".verified.json").read_text(encoding="utf-8"))["sha256"]
        == hashlib.sha256(b"abcdef").hexdigest()
    )


def test_existing_env_without_dotenv_emits_explicit_warning(tmp_path, monkeypatch, capsys):
    import builtins

    module, _ = configure_main(monkeypatch, tmp_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("DATA_DIR=./data\n", encoding="utf-8")
    original_import = builtins.__import__

    def without_dotenv(name, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("fixture missing python-dotenv")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_dotenv)
    assert module.main(["--only", "example", "--dry-run"]) == 0
    text = capsys.readouterr().out
    assert "dotenv" in text and ".env" in text


def test_vispoof_head_verified_manifest_remains_test_only_and_warns_vivos_overlap(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    import data_download_audio as audio

    listing = [
        SimpleNamespace(path=f"audio/audio_{index}.wav", id=f"drive-{index}") for index in range(2)
    ]
    listing_calls = []

    def drive_listing(**kwargs):
        listing_calls.append(kwargs)
        return listing

    monkeypatch.setitem(sys.modules, "gdown", SimpleNamespace(download_folder=drive_listing))
    heads, downloads = [], []

    class FakeClient:
        token = ""

        def head_size(self, url):
            heads.append(url)
            return 3

        def download(self, remote, dest):
            downloads.append(remote.path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"wav")

    dataset = core.Dataset("vispoofdb", "https://example.test", "unknown", 6, 20_000_000)
    plan = audio.prepare(dataset, FakeClient(), 2026, "small")
    assert len(heads) == 2 and not downloads
    assert listing_calls[0]["skip_download"] is True
    assert plan.peak_bytes >= 6
    plan.execute(tmp_path, FakeClient())
    rows = json.loads((tmp_path / "selected_manifest.json").read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert all(row["split_policy"] == "test_only" and row["subject_id"] is None for row in rows)
    assert {row["source_file_id"] for row in rows} == {"drive-0", "drive-1"}
    assert "vivos" in " ".join(plan.notes).lower()


def test_wild_csv_keeps_video_origins_across_archives_without_inventing_speakers(tmp_path):
    import csv

    import data_download_images as images

    payloads = {
        "data/fake_train/part-0.tar.gz": archive_bytes([("shared-video/000.jpg", b"a")], gzip=True),
        "data/fake_train/part-1.tar.gz": archive_bytes([("shared-video/001.jpg", b"b")], gzip=True),
        "data/real_train/part-0.tar.gz": archive_bytes([("real-video/000.jpg", b"c")], gzip=True),
    }

    class FakeClient:
        def hf_files(self, repo, prefix=""):
            return "revision", [
                {"path": path, "size": len(payload)} for path, payload in payloads.items()
            ]

        def download(self, remote, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payloads[remote.path])

    dataset = core.Dataset("wilddeepfake", "https://example.test", "unknown", 5_000_000, 5_000_000)
    plan = images.prepare(dataset, FakeClient(), 2026, "small")
    plan.execute(tmp_path, FakeClient())
    with (tmp_path / "index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert any("video_origin_id" in note and "nhiều archive" in note for note in plan.notes)
    shared = [row for row in rows if row["video_origin_id"] == "shared-video"]
    assert len(shared) == 2
    assert len({row["archive"] for row in shared}) == 2
    assert {row["source_video_id"] for row in shared} == {"fake_train::shared-video"}
    assert all(not row["speaker_id"] and not row["subject_id"] for row in rows)
    assert {row["member"] for row in rows} == {
        "shared-video/000.jpg",
        "shared-video/001.jpg",
        "real-video/000.jpg",
    }


def test_vicocktail_csv_connects_clips_from_multiple_archives_to_one_original(tmp_path):
    import csv

    import data_download_images as images

    original = "abcdefghijk"
    payloads = {
        f"data/avvn-train-{index:03}.tar": archive_bytes(
            [
                (f"clip-{index}.sample_id", f"{original}_{index}_original".encode()),
                (f"clip-{index}.video", b"video"),
                (f"clip-{index}.wav", b"audio"),
            ]
        )
        for index in range(2)
    }

    class FakeClient:
        def hf_files(self, repo, prefix=""):
            return "revision", [
                {"path": path, "size": len(payload)} for path, payload in payloads.items()
            ]

        def download(self, remote, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payloads[remote.path])

    dataset = core.Dataset("vicocktail", "https://example.test", "unknown", 5_000_000, 5_000_000)
    plan = images.prepare(dataset, FakeClient(), 2026, "small")
    plan.execute(tmp_path, FakeClient())
    with (tmp_path / "index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert {row["source_video_id"] for row in rows} == {original}
    assert {row["video_origin_id"] for row in rows} == {original}
    assert len({row["archive"] for row in rows}) == 2
    assert all(not row["speaker_id"] and not row["subject_id"] for row in rows)
    assert all(row["member"].endswith(".video") for row in rows)
    assert all(len(json.loads(row["members"])) == 3 for row in rows)


@pytest.mark.parametrize("subset", ["small", "full"])
def test_fas_vn_uses_single_pinned_aggregate_zip_not_per_image_downloads(subset):
    import data_download_images as images

    calls = []

    class FakeClient:
        kaggle_auth = ("fixture", "fake-key")

        def json(self, url, **kwargs):
            calls.append(("json", url))
            return {"currentVersionNumber": 7, "totalBytes": 8_392_841_360}

        def head_size(self, url, **kwargs):
            calls.append(("size", url))
            return 8_392_841_360

    dataset = core.Dataset(
        "fas_vn",
        "https://www.kaggle.com/datasets/maihongtng/face-anti-spoofing",
        "CC0",
        8_392_841_360,
        8_500_000_000,
    )
    plan = images.prepare(dataset, FakeClient(), 2026, subset)
    assert len(plan.files) == 1
    assert plan.files[0].path.endswith(".zip")
    assert plan.files[0].size == 8_392_841_360
    assert "datasetVersionNumber=7" in plan.files[0].url
    assert len(calls) == 2
    assert all("/list/" not in url for _, url in calls)


def test_main_reports_network_and_processing_timing_separately(tmp_path, monkeypatch):
    module, dataset = configure_main(monkeypatch, tmp_path)
    dataset.budget_bytes = 2_000_000
    now = [0.0]

    class TimedClient:
        token = ""
        kaggle_auth = None
        network_seconds = 0.0
        network_bytes = 0
        download_bytes = 0

        def __init__(self, **kwargs):
            pass

        def close(self):
            pass

    monkeypatch.setattr(module, "Client", TimedClient)
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(module, "_commit", lambda: "fixture-commit")

    def prepare(selected, client, seed, subset):
        client.network_seconds += 1.0
        client.network_bytes += 1000
        now[0] += 2.0

        def execute(dest, client):
            client.network_seconds += 2.0
            client.network_bytes += 2000
            client.download_bytes += 2000
            now[0] += 3.0

        return core.Plan(dataset, [], 0, execute=execute)

    monkeypatch.setattr(module, "prepare_dataset", prepare)
    assert module.main(["--only", "example"]) == 0
    reports = list((tmp_path / "new-data/runs").glob("*.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    outcome = report["outcomes"]["example"]
    assert outcome["seconds"] == pytest.approx(5.0)
    assert outcome["prepare_seconds"] == pytest.approx(2.0)
    assert outcome["execute_seconds"] == pytest.approx(3.0)
    for metrics in (outcome, report):
        assert metrics["network_seconds"] == pytest.approx(3.0)
        assert metrics["processing_seconds"] == pytest.approx(2.0)
        assert metrics["network_bytes"] == 3000
        assert metrics["network_mbps"] == pytest.approx(0.001)


def test_safe_path_survives_concurrent_creation_of_shared_parent(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    for attempt in range(8):
        root = tmp_path / f"batch-{attempt}"

        def create_file(index, dataset_root=root):
            try:
                target = core.safe_path(dataset_root, f"audio/shared-person/{index}.wav")
            except core.DownloadError as error:
                trace = error.__traceback__
                while trace is not None:
                    if trace.tb_frame.f_code.co_name == "safe_path":
                        actual = trace.tb_frame.f_locals
                        raise AssertionError(
                            f"Concurrent resolution base={actual.get('base')!r}, "
                            f"target={actual.get('target')!r}"
                        ) from error
                    trace = trace.tb_next
                raise
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture")
            return target

        with ThreadPoolExecutor(max_workers=16) as workers:
            paths = list(workers.map(create_file, range(32)))
        assert len(paths) == 32
        assert all(path.is_relative_to(root.resolve()) for path in paths)
        assert all(path.read_bytes() == b"fixture" for path in paths)


@pytest.mark.parametrize(
    "relative",
    [
        "../escape.wav",
        "audio/../../escape.wav",
        "C:\\outside\\escape.wav",
        "audio\\..\\..\\escape.wav",
        "/outside/escape.wav",
    ],
)
def test_safe_path_still_rejects_traversal_and_absolute_inputs(tmp_path, relative):
    with pytest.raises(core.DownloadError):
        core.safe_path(tmp_path / "dataset", relative)
    assert not (tmp_path / "escape.wav").exists()


@pytest.mark.parametrize("first_failure", ["503", "connection"])
def test_head_size_retries_transient_failure_without_body_or_real_sleep(monkeypatch, first_failure):
    attempts, pauses = [], []

    def handler(request):
        attempts.append(request.method)
        assert request.method == "HEAD"
        if len(attempts) == 1:
            if first_failure == "connection":
                raise httpx.ConnectError("fixture connection interrupted", request=request)
            return httpx.Response(503)
        return httpx.Response(200, headers={"Content-Length": "1234"})

    monkeypatch.setattr(core.time, "sleep", pauses.append)
    client = make_client(handler)
    assert client.head_size("https://example.test/audio.wav") == 1234
    assert attempts == ["HEAD", "HEAD"]
    assert pauses == [1]
    assert client.network_bytes == 0


def test_head_404_falls_back_to_range_headers_without_consuming_body():
    class ForbiddenBody(httpx.SyncByteStream):
        def __iter__(self):
            pytest.fail("size preflight must never read media body")
            yield b""

    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "HEAD":
            return httpx.Response(404)
        assert request.headers["Range"] == "bytes=0-0"
        return httpx.Response(
            206, headers={"Content-Range": "bytes 0-0/1234"}, stream=ForbiddenBody()
        )

    client = make_client(handler)
    assert client.head_size("https://example.test/audio.wav") == 1234
    assert [request.method for request in requests] == ["HEAD", "GET"]
    assert client.network_bytes == 0


def cached_head_client(cache_dir, handler):
    client = core.Client(
        token="private-hf-token", kaggle_auth=("private-user", "private-key"), cache_dir=cache_dir
    )
    client._http.close()
    client._http = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def test_head_cache_reused_by_second_client_and_contains_no_url_or_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(100_000_000_000, 0, 100_000_000_000),
    )
    cache = tmp_path / "metadata"
    url = "https://example.test/audio.wav?token=private-signed-query"
    requests = []

    def verified(request):
        requests.append(request)
        return httpx.Response(200, headers={"Content-Length": "1234"})

    first = cached_head_client(cache, verified)
    assert first.head_size(url) == 1234
    first.close()
    payload = (cache / "head_sizes.json").read_text(encoding="utf-8")
    assert set(json.loads(payload)) == {hashlib.sha256(url.encode()).hexdigest()}
    for sensitive in [
        url,
        "private-signed-query",
        "private-hf-token",
        "private-user",
        "private-key",
    ]:
        assert sensitive not in payload

    def no_network(request):
        pytest.fail("fresh verified size must survive a new client")

    second = cached_head_client(cache, no_network)
    assert second.head_size(url) == 1234
    second.close()
    assert len(requests) == 1


@pytest.mark.parametrize("cache_state", ["expired", "corrupt"])
def test_stale_or_corrupt_head_cache_is_refreshed(tmp_path, monkeypatch, cache_state):
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(100_000_000_000, 0, 100_000_000_000),
    )
    now = 100_000.0
    monkeypatch.setattr(core.time, "time", lambda: now)
    url = "https://example.test/audio.wav"
    path = tmp_path / "head_sizes.json"
    if cache_state == "corrupt":
        path.write_text("{not-json", encoding="utf-8")
    else:
        key = hashlib.sha256(url.encode()).hexdigest()
        path.write_text(
            json.dumps({key: {"size": 111, "verified_at": now - 86_401}}), encoding="utf-8"
        )
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, headers={"Content-Length": "222"})

    client = cached_head_client(tmp_path, handler)
    assert client.head_size(url) == 222
    client.close()
    assert len(requests) == 1
    assert (
        json.loads(path.read_text(encoding="utf-8"))[hashlib.sha256(url.encode()).hexdigest()][
            "size"
        ]
        == 222
    )


def test_head_cache_checkpoints_each_128_verified_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(
        core.shutil,
        "disk_usage",
        lambda _: shutil._ntuple_diskusage(100_000_000_000, 0, 100_000_000_000),
    )
    client = cached_head_client(
        tmp_path, lambda _: httpx.Response(200, headers={"Content-Length": "123"})
    )
    for index in range(128):
        assert client.head_size(f"https://example.test/audio/{index}") == 123
    path = tmp_path / "head_sizes.json"
    assert path.exists()
    assert len(json.loads(path.read_text(encoding="utf-8"))) == 128
    client.close()


def test_media_download_retries_503_then_verifies_atomic_result(tmp_path, monkeypatch):
    pauses, requests = [], []
    monkeypatch.setattr(core.time, "sleep", pauses.append)
    dest = tmp_path / "audio.wav"
    payload = b"complete-audio"

    def handler(request):
        requests.append(request)
        assert not dest.exists()
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(200, content=payload)

    client = make_client(handler)
    client.download(
        core.RemoteFile(
            "https://example.test/audio",
            "audio.wav",
            len(payload),
            hashlib.sha256(payload).hexdigest(),
        ),
        dest,
    )
    assert len(requests) == 2
    assert pauses == [1]
    assert dest.read_bytes() == payload
    assert not Path(str(dest) + ".part").exists()
    assert (
        json.loads(Path(str(dest) + ".verified.json").read_text(encoding="utf-8"))["sha256"]
        == hashlib.sha256(payload).hexdigest()
    )


def test_media_read_interruption_retries_from_verified_partial_offset(tmp_path, monkeypatch):
    pauses, requests = [], []
    monkeypatch.setattr(core.time, "sleep", pauses.append)
    dest = tmp_path / "audio.wav"
    prefix = b"a" * core.CHUNK_BYTES
    suffix = b"abcdef"
    payload = prefix + suffix

    class InterruptedBody(httpx.SyncByteStream):
        def __iter__(self):
            yield prefix
            raise httpx.ReadError("fixture interrupted after a complete chunk")

    def handler(request):
        requests.append(request)
        assert not dest.exists()
        if len(requests) == 1:
            assert "Range" not in request.headers
            return httpx.Response(
                200, headers={"Content-Length": str(len(payload))}, stream=InterruptedBody()
            )
        assert Path(str(dest) + ".part").read_bytes() == prefix
        assert request.headers["Range"] == f"bytes={len(prefix)}-"
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {len(prefix)}-{len(payload) - 1}/{len(payload)}"},
            content=suffix,
        )

    client = make_client(handler)
    client.download(
        core.RemoteFile(
            "https://example.test/audio",
            "audio.wav",
            len(payload),
            hashlib.sha256(payload).hexdigest(),
        ),
        dest,
    )
    assert len(requests) == 2
    assert pauses == [1]
    assert dest.read_bytes() == payload
    assert not Path(str(dest) + ".part").exists()
    assert client.download_bytes == len(payload)
