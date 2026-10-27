"""Key generation must be idempotent without secret output or overwriting old material."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "gen_keys.py"
spec = importlib.util.spec_from_file_location("vericlue_gen_keys_test", SCRIPT)
keys = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keys)


def test_generation_rerun_and_no_secret_output(tmp_path, capsys):
    directory = tmp_path / "server-signing"
    assert keys.main(["--out", str(directory)]) == 0
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    assert keys.main(["--out", str(directory)]) == 0
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before
    out = capsys.readouterr()
    assert before["session-signing-secret.txt"].decode().strip() not in out.out
    assert "PRIVATE KEY" not in out.out and not out.err
    assert (
        keys.public_key_fingerprint(keys.load_public_key(directory / "ed25519-public.pem"))
        in out.out
    )


@pytest.mark.parametrize("fault", ["partial", "mismatch", "invalid_secret"])
def test_existing_invalid_bundle_is_not_overwritten(tmp_path, fault):
    directory = tmp_path / "keys"
    keys.generate(directory)
    if fault == "partial":
        (directory / "ed25519-public.pem").unlink()
    elif fault == "mismatch":
        other = tmp_path / "other"
        keys.generate(other)
        (directory / "ed25519-public.pem").write_bytes((other / "ed25519-public.pem").read_bytes())
    else:
        (directory / "session-signing-secret.txt").write_text("too short")
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    assert keys.main(["--out", str(directory)]) == 1
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == before
