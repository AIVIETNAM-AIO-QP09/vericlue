"""Private worker + transaction completion using synthetic verdicts/media/vectors."""

import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from time import monotonic, perf_counter, sleep

import pytest
from sqlalchemy import func, select
from test_accounts import prepared, real_settings, verdict
from test_accounts import private_client as private_client

from vericlue_api.core.config import Settings
from vericlue_api.core.errors import ApiError
from vericlue_api.db.models import AccountRow, DecisionRow, SessionRow, utcnow
from vericlue_api.services.accounts import AccountStore
from vericlue_api.services.enrollment import EnrollmentService
from vericlue_api.services.orchestrator import Orchestrator
from vericlue_api.services.session_privacy import PlaintextLease
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Module
from vericlue_ml.face.template import FaceTemplate
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION, VideoFaceMatchDetector
from vericlue_ml.mock.detectors import MockDetector


def template():
    return FaceTemplate(
        session_id="ses_synthetic",
        challenge_id="synthetic-challenge",
        model_version=VIDEO_MATCH_VERSION,
        preprocessing="arcface112-rgb-minus1to1-v1",
        source_video_sha256="c" * 64,
        pixels_sha256="d" * 64,
        embedding=(1.0, *([0.0] * 511)),
    )


class SyntheticVideoDetector(VideoFaceMatchDetector):
    def __init__(self, action):
        # No model, runtime or camera is loaded in engineering tests.
        self.action = action

    def preload(self, **kwargs):
        pass

    def enrollment_template(self, inp, approved):
        return self.action(inp, approved)

    def predict(self, inp):
        return verdict(Module.FACE_MATCH, VIDEO_MATCH_VERSION)


def scheduler(action, *, queue=0, mock=False):
    detector = SyntheticVideoDetector(action)
    settings = Settings(
        _env_file=None,
        use_mock_models=mock,
        identity_lab_url="http://127.0.0.1:1",
        identity_face_from_video=True,
        detector_queue_size=queue,
        session_model_timeout_seconds=2,
    )
    instance = Orchestrator(
        settings,
        detector_factory=lambda m: detector if m == Module.FACE_MATCH else MockDetector(m),
    )
    instance.start()
    return instance, detector


def extract(instance, **kwargs):
    return instance.extract_template(
        DetectorInput(session_id="ses_synthetic"),
        verdict(Module.FACE_MATCH, VIDEO_MATCH_VERSION),
        **kwargs,
    )


def test_private_operation_uses_loaded_worker_and_does_not_log_vectors(caplog):
    threads = []

    def action(inp, approved):
        threads.append(threading.get_ident())
        assert inp.session_id == "ses_synthetic" and approved.gate == "pass"
        return template()

    instance, detector = scheduler(action)
    try:
        assert extract(instance) == template()
        assert extract(instance) == template()
        assert instance.loaded_detector(Module.FACE_MATCH) is detector
        assert all(t != threading.get_ident() for t in threads)
        assert "embedding" not in caplog.text and "1.0, 0.0" not in caplog.text
    finally:
        instance.close()


def test_enrolled_matching_uses_loaded_face_worker_and_keeps_vector_outside_metadata(monkeypatch):
    from vericlue_api.services import orchestrator
    from vericlue_ml.face.enrolled import REAUTH_MATCH_VERSION

    calls = []
    instance, detector = scheduler(lambda *_: template())

    def compare(loaded, inp, reference, artifact):
        assert loaded is detector and reference == template()
        assert "embedding" not in repr(inp) and "embedding" not in inp.model_dump_json()
        calls.append(threading.get_ident())
        return verdict(Module.FACE_MATCH, REAUTH_MATCH_VERSION)

    monkeypatch.setattr(orchestrator, "match_enrolled", compare)
    try:
        result = instance.run(
            [Module.FACE_MATCH],
            session_id="ses_current",
            scenario="genuine",
            reference_template=template(),
            extra_metadata={"purpose": "reauth"},
        )
        assert result[Module.FACE_MATCH].model_version == REAUTH_MATCH_VERSION
        assert calls and calls[0] != threading.get_ident()
        assert extract(instance) == template()  # Same cached instance still serves enrollment.
    finally:
        instance.close()


def test_timeout_keeps_plaintext_until_native_finishes_and_rejects_overflow(tmp_path):
    ready, release = threading.Event(), threading.Event()
    directory = tempfile.TemporaryDirectory(dir=tmp_path)
    decoded = Path(directory.name) / "synthetic.mp4"
    decoded.write_bytes(b"synthetic")
    lease = PlaintextLease(directory)
    calls = []

    def action(*_):
        calls.append(1)
        ready.set()
        assert release.wait(3)
        assert decoded.read_bytes() == b"synthetic"
        return template()

    instance, _ = scheduler(action)
    try:
        with pytest.raises(ApiError, match="ghi danh"):
            extract(instance, deadline=perf_counter() + 0.15, media_lease=lease)
        lease.release()
        assert ready.is_set() and decoded.exists()
        with pytest.raises(ApiError):
            extract(instance)
        # Face matching and template extraction share the same busy module slot.
        result = instance.run([Module.FACE_MATCH], session_id="ses_other", scenario="genuine")
        assert result[Module.FACE_MATCH].error_code == "E_TIMEOUT"
        assert calls == [1]
    finally:
        release.set()
        instance.close()
    end = monotonic() + 3
    while decoded.exists() and monotonic() < end:
        sleep(0.01)
    assert not decoded.exists()


@pytest.mark.parametrize("fault", ["mock", "expired", "closed", "exception", "invalid"])
def test_unavailable_or_invalid_private_jobs_never_return_a_template(fault):
    def action(*_):
        if fault == "exception":
            raise RuntimeError("private model detail must stay internal")
        if fault == "invalid":
            return template().model_copy(update={"embedding": (1.0,)})
        return template()

    instance, _ = scheduler(action, mock=fault == "mock")
    if fault == "closed":
        instance.close()
    try:
        with pytest.raises(ApiError) as caught:
            extract(instance, **({"deadline": perf_counter() - 1} if fault == "expired" else {}))
        assert caught.value.error_code == "enrollment_unavailable"
        assert "private model detail" not in str(caught.value)
    finally:
        instance.close()


def test_close_releases_queued_private_job_lease(tmp_path):
    ready, release = threading.Event(), threading.Event()

    def action(*_):
        ready.set()
        assert release.wait(3)
        return template()

    instance, _ = scheduler(action, queue=1)
    directory = tempfile.TemporaryDirectory(dir=tmp_path)
    decoded = Path(directory.name) / "queued.mp4"
    decoded.write_bytes(b"synthetic")
    lease = PlaintextLease(directory)
    try:
        with ThreadPoolExecutor(2) as callers:
            first = callers.submit(extract, instance)
            assert ready.wait(2)
            second = callers.submit(extract, instance, media_lease=lease)
            end = monotonic() + 2
            while not instance._queues[Module.FACE_MATCH] and monotonic() < end:
                sleep(0.01)
            assert len(instance._queues[Module.FACE_MATCH]) == 1
            lease.release()
            assert decoded.exists()
            instance.close()
            with pytest.raises(ApiError):
                second.result(1)
            assert not decoded.exists()
            release.set()
            assert first.result(1) == template()
    finally:
        release.set()
        instance.close()


def prepare_media(state):
    session, value, continuity = prepared(state)
    session.results[Module.FACE_CONTINUITY] = continuity
    root = Path(state.settings.media_dir) / session.session_id
    root.mkdir(parents=True)
    for field, name in (("video", "face.mp4"), ("id_front", "card.jpg")):
        path = root / name
        path.write_bytes(
            state.privacy.seal_media(session.session_id, name, b"synthetic-" + field.encode())
        )
        setattr(session, field, path)
    return session, value


def test_coordinator_decrypts_server_sources_and_stores_only_encrypted_template(private_client):
    root = private_client.app.state.vericlue
    decoded_paths = []
    with root.transaction() as state:
        session, value = prepare_media(state)

        def worker(inp, approved, *, deadline, media_lease):
            decoded_paths.extend((inp.video, inp.reference_image))
            assert inp.video.read_bytes() == b"synthetic-video"
            assert inp.reference_image.read_bytes() == b"synthetic-id_front"
            assert (
                inp.metadata["expected_challenge"]["challenge_id"] == session.challenge.challenge_id
            )
            assert approved is session.results[Module.FACE_MATCH] and media_lease is not None
            assert deadline == 123
            return value

        service = EnrollmentService(
            AccountStore(real_settings(state), state.db), state.privacy, worker, deadline=123
        )
        receipt = service.complete(session)
        assert service.complete(session) == receipt
        assert all(not path.exists() for path in decoded_paths)
        assert state.accounts.get(receipt.account_id).template == value
        assert "embedding" not in str(state.sessions._snapshot(session))
        assert not session.device_verified


@pytest.mark.parametrize(
    "fault", ["degraded", "continuity", "missing_video", "missing_card", "mock"]
)
def test_preflight_rejects_ineligible_session_before_worker(private_client, fault):
    with private_client.app.state.vericlue.transaction() as state:
        session, _ = prepare_media(state)
        settings = real_settings(state)
        if fault == "degraded":
            session.results[Module.FACE_PAD] = verdict(Module.FACE_PAD, status="degraded")
        elif fault == "continuity":
            session.results.pop(Module.FACE_CONTINUITY)
        elif fault == "missing_video":
            session.video = None
        elif fault == "missing_card":
            session.id_front = None
        else:
            settings = state.settings

        def forbidden(*args, **kwargs):
            pytest.fail("An ineligible session must not extract a template")

        with pytest.raises(ApiError):
            EnrollmentService(AccountStore(settings, state.db), state.privacy, forbidden).complete(
                session
            )
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 0


@pytest.mark.parametrize("fault", ["expired", "wrong_template", "worker_failure"])
def test_post_worker_failure_cannot_write_account(private_client, fault):
    with private_client.app.state.vericlue.transaction() as state:
        session, value = prepare_media(state)

        def worker(*args, **kwargs):
            if fault == "worker_failure":
                raise ApiError(503, "enrollment_unavailable", "Chưa thể hoàn tất ghi danh.")
            if fault == "expired":
                session.token_expires_at = utcnow() - timedelta(seconds=1)
            if fault == "wrong_template":
                return value.model_copy(update={"source_video_sha256": "e" * 64})
            return value

        with pytest.raises(ApiError):
            EnrollmentService(
                AccountStore(real_settings(state), state.db), state.privacy, worker
            ).complete(session)
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 0
        assert not list((Path(state.settings.media_dir) / "_decoded").glob("lease-*"))


def voice_ready(state, session=None):
    if session is None:
        session, _, _ = prepared(state)
    session.completed = False
    session.voice_requested = session.voice_owed = True
    session.voice_expires_at = utcnow() + timedelta(seconds=30)
    session.accepted_steps.remove("voice")
    state.db.get(SessionRow, session.session_id).status = "incomplete"
    state.flow._run = lambda modules, **kwargs: {
        m: MockDetector(m).predict(DetectorInput(metadata={"scenario": "genuine"})) for m in modules
    }
    state.flow.settings = state.settings.model_copy(update={"account_enrollment": True})
    return session


def test_voice_pass_returns_only_public_receipt_after_atomic_enrollment(private_client):
    from vericlue_api.services.accounts import AccountReceipt

    with private_client.app.state.vericlue.transaction() as state:
        session = voice_ready(state)
        seen = []

        def enroll(s):
            assert s.completed and not s.voice_requested and not s.voice_owed
            assert state.db.get(SessionRow, s.session_id).status == "pass"
            seen.append(s.session_id)
            return AccountReceipt("acct_" + "a" * 32, "dev_" + "b" * 32, utcnow())

        state.flow._enroll = enroll
        response = state.flow.voice(session)
        assert response.status == "pass"
        assert response.account.account_id == "acct_" + "a" * 32
        assert set(response.account.model_dump()) == {"account_id", "device_id", "expires_at"}
        assert seen == [session.session_id]


@pytest.mark.parametrize(
    "purpose,enabled", [("recovery", True), ("reauth", True), (None, True), ("onboarding", False)]
)
def test_hook_is_limited_to_opt_in_onboarding(private_client, purpose, enabled):
    with private_client.app.state.vericlue.transaction() as state:
        session = voice_ready(state)
        session.purpose = purpose
        state.flow.settings = state.settings.model_copy(update={"account_enrollment": enabled})

        def forbidden(_):
            pytest.fail("This flow must not create a new onboarding account")

        state.flow._enroll = forbidden
        assert state.flow.voice(session).status == "pass"


@pytest.mark.parametrize("mode", [False, "mixed"])
def test_flag_cannot_open_incomplete_real_or_mixed_dynamic_flows(private_client, mode):
    from vericlue_api.schemas.session import CreateSessionRequest

    with private_client.app.state.vericlue.transaction() as state:
        state.flow.settings = state.settings.model_copy(
            update={"account_enrollment": True, "use_mock_models": mode}
        )
        with pytest.raises(ApiError) as caught:
            state.flow.create(
                "genuine",
                CreateSessionRequest(purpose="onboarding", nonce="synthetic-nonce-12345678"),
            )
        assert caught.value.error_code == "flow_unavailable"
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 0


def test_enrollment_failure_rolls_back_the_pass_decision_and_step(private_client):
    root = private_client.app.state.vericlue
    with root.transaction() as state:
        sid = voice_ready(state).session_id
        count = state.db.scalar(select(func.count()).select_from(DecisionRow))
    with pytest.raises(ApiError), root.transaction() as state:
        session = state.sessions.get(sid)
        state.flow.settings = state.settings.model_copy(update={"account_enrollment": True})
        state.flow._run = lambda modules, **kwargs: {
            m: MockDetector(m).predict(DetectorInput(metadata={"scenario": "genuine"}))
            for m in modules
        }

        def fail(_):
            raise ApiError(503, "enrollment_unavailable", "Chưa thể hoàn tất ghi danh.")

        state.flow._enroll = fail
        state.flow.voice(session)
    with root.transaction() as state:
        session = state.sessions.get(sid)
        assert not session.completed and session.voice_requested
        assert "voice" not in session.accepted_steps
        assert state.db.get(SessionRow, sid).status == "incomplete"
        assert state.db.scalar(select(func.count()).select_from(DecisionRow)) == count
        assert state.db.scalar(select(func.count()).select_from(AccountRow)) == 0
