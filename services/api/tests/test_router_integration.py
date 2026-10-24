"""ROUT-02 API policy integration using CPU mocks and isolated SQLite databases."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from vericlue_api.core.config import get_settings
from vericlue_api.db.models import DecisionRow, ModuleResultRow, ReviewCaseRow, SessionRow
from vericlue_api.main import create_app
from vericlue_ml.common.result import Gate, Module, ModuleResult, Status

ROOT = Path(__file__).resolve().parents[3]
PRIVATE_KEYS = {
    "score",
    "prob_attack",
    "evidence",
    "lambda",
    "Lambda",
    "thresholds",
    "reason",
    "config_version",
    "config_hash",
    "transcript",
    "recognized_text",
    "expected_text",
    "wer",
}


def assert_citizen_payload(value):
    if isinstance(value, dict):
        assert not PRIVATE_KEYS.intersection(value)
        for child in value.values():
            assert_citizen_payload(child)
    elif isinstance(value, list):
        for child in value:
            assert_citizen_payload(child)
    elif isinstance(value, str):
        assert "giả mạo" not in value.lower()


def create_session(client, scenario):
    response = client.post("/v1/sessions", headers={"X-Mock-Scenario": scenario})
    assert response.status_code == 200
    assert_citizen_payload(response.json())
    created = response.json()
    return created["session_id"], {"Authorization": "Bearer " + created["token"]}


def finalize(client, sid, auth):
    response = client.post(f"/v1/sessions/{sid}/finalize", headers=auth)
    assert_citizen_payload(response.json())
    return response


def voice(client, sid, auth):
    response = client.post(
        f"/v1/sessions/{sid}/voice",
        headers=auth,
        files={"audio": ("voice.wav", b"synthetic audio", "audio/wav")},
    )
    assert_citizen_payload(response.json())
    return response


class FixedDetector:
    def __init__(self, result):
        self.name = Module(result.module)
        self.version = result.model_version
        self.result = result

    def predict(self, _inp):
        return self.result.model_copy(deep=True)


def install_result(client, module, *, gate=None, probability=None, version="mock@router-test"):
    result = ModuleResult(
        module=module,
        model_version=version,
        status=Status.OK,
        gate=gate,
        score=probability,
        prob_attack=probability,
        latency_ms=0,
    )
    client.app.state.vericlue.orchestrator._detectors[module] = FixedDetector(result)


@pytest.mark.parametrize(
    "scenario, expected",
    [
        ("genuine", "pass"),
        ("print", "review"),
        ("replay", "review"),
        ("virtual_cam", "review"),
        ("faceswap", "review"),
        ("voice_clone", "voice_challenge"),
        ("low_quality", "retry"),
    ],
)
def test_router_all_agreed_mock_scenarios(client, scenario, expected):
    sid, auth = create_session(client, scenario)
    response = finalize(client, sid, auth)
    assert response.status_code == 200
    assert response.json()["status"] == expected
    if scenario == "voice_clone":
        spoken = voice(client, sid, auth)
        assert spoken.status_code == 200
        assert spoken.json() == {"status": "review"}
    if scenario == "low_quality":
        assert response.json()["attempts_left"] == 1
        second = finalize(client, sid, auth)
        assert second.status_code == 200
        assert second.json()["status"] == "retry"
        assert second.json()["attempts_left"] == 0
        third = finalize(client, sid, auth)
        assert third.status_code == 200
        assert third.json() == {"status": "review"}
        with client.app.state.vericlue.database.sessions() as db:
            stored = db.get(SessionRow, sid)
            assert stored.payload["retries_used"] == 2
            assert stored.payload["case_id"]
            actions = db.scalars(
                select(DecisionRow.action)
                .where(DecisionRow.session_id == sid)
                .order_by(DecisionRow.id)
            ).all()
            assert actions == ["retry", "retry", "review"]


def test_router_error_scenario_never_passes(client):
    sid, auth = create_session(client, "error")
    response = finalize(client, sid, auth)
    assert response.status_code == 200
    assert response.json() == {"status": "review"}


def test_router_preserves_voice_not_requested_guard_before_file_write(client):
    sid, auth = create_session(client, "genuine")
    response = voice(client, sid, auth)
    assert response.status_code == 409
    assert response.json()["error_code"] == "voice_not_requested"
    folder = Path(client.app.state.vericlue.settings.media_dir) / sid
    assert not list(folder.glob("voice_audio.*"))


@pytest.mark.parametrize("step", ["finalize", "voice"])
def test_router_preserves_session_closed_guard(client, step):
    sid, auth = create_session(client, "print")
    assert finalize(client, sid, auth).json() == {"status": "review"}
    response = finalize(client, sid, auth) if step == "finalize" else voice(client, sid, auth)
    assert response.status_code == 409
    assert response.json()["error_code"] == "session_closed"
    with client.app.state.vericlue.database.sessions() as db:
        rows = db.scalars(select(DecisionRow).where(DecisionRow.session_id == sid)).all()
        assert len(rows) == 1


def test_router_voice_reread_counter_remains_owned_by_session_flow(client):
    sid, auth = create_session(client, "voice_clone")
    requested = finalize(client, sid, auth)
    assert requested.status_code == 200
    first_prompt = requested.json()["voice_prompt"]
    install_result(client, Module.VOICE_CHALLENGE, gate=Gate.FAIL)
    install_result(client, Module.VOICE_SPOOF, probability=0.01)
    install_result(client, Module.LIPSYNC, probability=0.01)
    first = voice(client, sid, auth)
    assert first.status_code == 200
    assert first.json()["status"] == "voice_challenge"
    assert first.json()["attempts_left"] == 0
    assert first.json()["voice_prompt"] != first_prompt
    second = voice(client, sid, auth)
    assert second.status_code == 200
    assert second.json() == {"status": "review"}
    with client.app.state.vericlue.database.sessions() as db:
        row = db.get(SessionRow, sid)
        assert row.payload["voice_rereads_used"] == 1
        assert row.payload["voice_requested"] is False


def test_router_decision_records_exact_config_hash_and_threshold_snapshot(client):
    sid, auth = create_session(client, "genuine")
    assert finalize(client, sid, auth).json() == {"status": "pass"}
    config_bytes = (ROOT / "ml/configs/thresholds.yaml").read_bytes()
    expected_version = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
    with client.app.state.vericlue.database.sessions() as db:
        decisions = db.scalars(select(DecisionRow).where(DecisionRow.session_id == sid)).all()
        assert len(decisions) == 1
        decision = decisions[0]
        assert decision.config_version == expected_version
        assert len(decision.config_version) == 71
        assert decision.thresholds
        snapshot = json.dumps(decision.thresholds)
        assert "provisional" in snapshot
        assert "voice" in snapshot


def test_router_requires_calibrator_for_real_version_even_with_low_probability(
    client, monkeypatch, tmp_path
):
    monkeypatch.setenv("CALIBRATORS_DIR", str(tmp_path / "missing-calibrators"))
    sid, auth = create_session(client, "genuine")
    install_result(client, Module.FACE_PAD, probability=0.001, version="real-pad@no-calibrator")
    response = finalize(client, sid, auth)
    assert response.status_code == 200
    assert response.json() == {"status": "review"}

    with client.app.state.vericlue.database.sessions() as db:
        result = db.scalar(
            select(ModuleResultRow).where(
                ModuleResultRow.session_id == sid,
                ModuleResultRow.module == "face_pad",
            )
        )
        assert result is not None
        assert result.status == "error"
        assert result.prob_attack is None
        assert result.payload.get("prob_attack") is None
        stored_session = db.get(SessionRow, sid)
        assert stored_session.payload["results"]["face_pad"]["status"] == "error"
        assert stored_session.payload["results"]["face_pad"].get("prob_attack") is None


def test_router_mock_versions_do_not_need_calibrators(client, monkeypatch, tmp_path):
    monkeypatch.setenv("CALIBRATORS_DIR", str(tmp_path / "missing-calibrators"))
    sid, auth = create_session(client, "genuine")
    assert finalize(client, sid, auth).json() == {"status": "pass"}


def test_router_custom_config_is_loaded_once_at_startup(monkeypatch, tmp_path):
    original = (
        ROOT / "ml/configs/thresholds.yaml"
    ).read_bytes() + b"\n# isolated API config fixture\n"
    custom = tmp_path / "routing.yaml"
    custom.write_bytes(original)
    monkeypatch.setenv("THRESHOLDS_CONFIG", str(custom))
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            custom.write_bytes(b"invalid_yaml: [\n")
            sid, auth = create_session(client, "genuine")
            response = finalize(client, sid, auth)
            assert response.status_code == 200
            assert response.json() == {"status": "pass"}
            with client.app.state.vericlue.database.sessions() as db:
                decision = db.scalar(select(DecisionRow).where(DecisionRow.session_id == sid))
                assert decision.config_version == "sha256:" + hashlib.sha256(original).hexdigest()
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("voice_threshold, expected", [(0.15, "review"), (0.30, "pass")])
def test_router_voice_uses_yaml_voice_threshold_instead_of_face_b(
    monkeypatch, tmp_path, voice_threshold, expected
):
    import yaml

    config = yaml.safe_load((ROOT / "ml/configs/thresholds.yaml").read_text(encoding="utf-8"))
    config["face"]["b"] = 0.40
    config["face"]["a"] = 0.80
    config["voice"]["spoof_threshold"] = voice_threshold
    custom = tmp_path / "voice-policy.yaml"
    custom.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    expected_version = "sha256:" + hashlib.sha256(custom.read_bytes()).hexdigest()
    monkeypatch.setenv("THRESHOLDS_CONFIG", str(custom))
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            sid, auth = create_session(client, "voice_clone")
            response = finalize(client, sid, auth)
            assert response.status_code == 200
            assert response.json()["status"] == "voice_challenge"
            install_result(client, Module.VOICE_SPOOF, probability=0.20)
            install_result(client, Module.LIPSYNC, probability=0.20)
            spoken = voice(client, sid, auth)
            assert spoken.status_code == 200
            assert spoken.json() == {"status": expected}
            with client.app.state.vericlue.database.sessions() as db:
                decisions = db.scalars(
                    select(DecisionRow)
                    .where(DecisionRow.session_id == sid)
                    .order_by(DecisionRow.id)
                ).all()
                assert len(decisions) == 2
                for decision in decisions:
                    assert decision.config_version == expected_version
                    assert decision.thresholds["face"]["b"] == 0.40
                    assert decision.thresholds["face"]["a"] == 0.80
                    assert decision.thresholds["face"]["sources"] == config["face"]["sources"]
                    assert decision.thresholds["voice"]["spoof_threshold"] == voice_threshold
                    assert (
                        decision.thresholds["voice"]["max_syllable_wer"]
                        == config["voice"]["max_syllable_wer"]
                    )
                    assert (
                        decision.thresholds["voice"]["min_unaccented_similarity"]
                        == config["voice"]["min_unaccented_similarity"]
                    )
                    assert decision.thresholds["provisional"] is True
                    assert decision.thresholds["fusion"]["method"] == "max"
    finally:
        get_settings.cache_clear()


def expire_session_field(client, sid, field):
    expired = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    with client.app.state.vericlue.database.sessions.begin() as db:
        row = db.get(SessionRow, sid)
        payload = dict(row.payload)
        if field == "challenge":
            payload["challenge"] = dict(payload["challenge"], expires_at=expired)
        else:
            payload["token_expires_at"] = expired
        row.payload = payload


@pytest.mark.parametrize(
    "step, expired_field", [("finalize", "token"), ("finalize", "challenge"), ("voice", "token")]
)
def test_router_expired_context_is_rejected_without_inference_or_new_decision(
    client, monkeypatch, step, expired_field
):
    sid, auth = create_session(client, "voice_clone" if step == "voice" else "genuine")
    if step == "voice":
        assert finalize(client, sid, auth).json()["status"] == "voice_challenge"
    with client.app.state.vericlue.database.sessions() as db:
        before = list(db.scalars(select(DecisionRow.id).where(DecisionRow.session_id == sid)))
    expire_session_field(client, sid, expired_field)

    def forbidden_inference(*_args, **_kwargs):
        raise AssertionError("Expired session context must be handled before detector submission")

    monkeypatch.setattr(client.app.state.vericlue.orchestrator, "run", forbidden_inference)
    response = finalize(client, sid, auth) if step == "finalize" else voice(client, sid, auth)
    assert response.status_code == (401 if expired_field == "token" else 409)
    assert response.json()["error_code"] == (
        "unauthorized" if expired_field == "token" else "challenge_expired"
    )
    with client.app.state.vericlue.database.sessions() as db:
        case = db.scalar(select(ReviewCaseRow).where(ReviewCaseRow.session_id == sid))
        assert case is None
        after = list(db.scalars(select(DecisionRow.id).where(DecisionRow.session_id == sid)))
        assert after == before


def test_router_expired_context_does_not_bypass_bad_token_401(client):
    sid, _ = create_session(client, "genuine")
    expire_session_field(client, sid, "token")
    response = finalize(client, sid, {"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401
    assert response.json()["error_code"] == "unauthorized"
    with client.app.state.vericlue.database.sessions() as db:
        assert db.scalar(select(ReviewCaseRow).where(ReviewCaseRow.session_id == sid)) is None
        assert db.scalar(select(DecisionRow).where(DecisionRow.session_id == sid)) is None


def test_router_voice_does_not_reuse_color_challenge_expiration(client):
    sid, auth = create_session(client, "voice_clone")
    assert finalize(client, sid, auth).json()["status"] == "voice_challenge"
    expire_session_field(client, sid, "challenge")
    install_result(client, Module.VOICE_SPOOF, probability=0.01)
    install_result(client, Module.LIPSYNC, probability=0.01)
    response = voice(client, sid, auth)
    assert response.status_code == 200
    assert response.json() == {"status": "pass"}
