"""Uploaded video, not the client still, supplies the server-selected identity pixels."""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from synthetic_images import synthetic_image
from test_dynamic_flows import create

from vericlue_api.core.config import get_settings
from vericlue_api.main import create_app
from vericlue_api.services import orchestrator as orchestration
from vericlue_api.services.identity_runtime import IdentityRuntime
from vericlue_ml.common.result import Module
from vericlue_ml.face import video_match
from vericlue_ml.face.match import ARCFACE_TARGET
from vericlue_ml.face.pad import FaceBox
from vericlue_ml.face.video_match import VIDEO_MATCH_VERSION, VideoFaceMatchDetector
from vericlue_ml.presence.landmarks import FaceObservation
from vericlue_ml.presence.views import SelectedFrame


def test_api_uses_bound_video_frame_even_when_uploaded_still_is_not_an_image(monkeypatch):
    cv2 = pytest.importorskip("cv2")
    monkeypatch.setenv("IDENTITY_LAB_URL", "http://127.0.0.1:8010")
    monkeypatch.setenv("IDENTITY_FACE_FROM_VIDEO", "true")
    monkeypatch.delenv("FACE_MATCH_CALIBRATION", raising=False)
    monkeypatch.delenv("IDENTITY_FACE_CALIBRATION", raising=False)
    instances, selected = [], []

    class Reader:
        def preload(self, **kwargs):
            pass

        def observe(self, pixels, *, at_ms):
            assert np.all(pixels == 100)
            return FaceObservation(at_ms, 1, yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0)

    class Finder:
        def find(self, pixels):
            return [FaceBox(5, 5, 105, 105, 0.99, ARCFACE_TARGET)]

    class Embedder:
        def embed(self, tensor):
            return np.ones(512, dtype=np.float32)

    class SyntheticVideoMatcher(VideoFaceMatchDetector):
        def __init__(self, *, reader, **kwargs):
            super().__init__(reader=Reader(), finder=Finder(), embedder=Embedder(), **kwargs)
            instances.append(self)

    def pick(path, target):
        selected.append((path, target))
        return SelectedFrame(target, target, np.full((140, 140, 3), 100, np.uint8))

    monkeypatch.setattr(orchestration, "VideoFaceMatchDetector", SyntheticVideoMatcher)
    monkeypatch.setattr(video_match, "select_frontal_frame", pick)
    monkeypatch.setattr(
        IdentityRuntime,
        "scan",
        lambda *_: {
            "qr_values": ["001099012345||Test Person|01011995|Nam|Synthetic Address|15062021"],
            "fields": {},
        },
    )
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        created, auth = create(client)
        endpoint = f"/v1/sessions/{created['session_id']}"
        ok, png = cv2.imencode(".png", np.full((140, 140, 3), 30, np.uint8))
        assert ok
        response = client.post(
            endpoint + "/id-card",
            headers=auth,
            files={
                "front": ("front.png", png.tobytes(), "image/png"),
                "back": ("back.png", png.tobytes(), "image/png"),
            },
        )
        assert response.status_code == 200
        assert (
            client.post(
                endpoint + "/id-card/confirm", headers=auth, json=response.json()["fields"]
            ).status_code
            == 200
        )
        cid = created["challenge"]["challenge_id"]
        assert (
            client.post(
                endpoint + "/media",
                headers=auth,
                data={"challenge_id": cid},
                files={
                    "image": ("forged.jpg", synthetic_image(b"not an image"), "image/jpeg"),
                    "video": ("video.mp4", b"\0\0\0\x18ftyp" + b"0" * 16, "video/mp4"),
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                endpoint + "/signals",
                headers=auth,
                json={
                    "challenge_id": cid,
                    "color_events": [],
                    "frame_times": [],
                },
            ).status_code
            == 200
        )
        response = client.post(endpoint + "/finalize", headers=auth, json={"challenge_id": cid})
        assert response.json()["status"] == "review"  # No real calibration artifact.
        assert len(instances) == 1 and len(selected) == 1
        assert selected[0][1] == created["challenge"]["dynamic"]["frontal_capture_at_ms"]
        with client.app.state.vericlue.transaction() as state:
            session = state.sessions.get(created["session_id"])
            assert selected[0][0] == session.video
            result = session.results[Module.FACE_MATCH]
            assert result.model_version == VIDEO_MATCH_VERSION
            assert result.status == "degraded" and result.quality["frontal_pose_checked"]
        assert not any(word in response.text for word in ("score", "cosine", "pixels_sha256"))


def test_opt_in_detectors_share_one_task_owner():
    from vericlue_api.core.config import Settings

    orchestrator = orchestration.Orchestrator(
        Settings(
            identity_lab_url="http://127.0.0.1:8010",
            identity_face_from_video=True,
            session_face_checks=True,
        )
    )
    for module in (Module.FACE_MATCH, Module.GAZE_TRACKING, Module.HEAD_TURN):
        assert orchestrator._default_detector(module).reader is orchestrator._face_reader
