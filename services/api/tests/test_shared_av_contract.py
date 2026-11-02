"""Shared-container transport/proofs with synthetic PCM; no native codecs or models."""

import io
import wave

import pytest
from test_media_proof import create, face_outcome, send_face, sign

from vericlue_ml.face.continuity import wav_duration
from vericlue_ml.presence.landmarks import LandmarkError


def synthetic_wav(*, rate=16000, channels=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\x01\x00" * rate * 2 * channels)
    return output.getvalue()


@pytest.mark.parametrize(
    "rate,channels,accepted", [(16000, 1, True), (48000, 1, False), (48000, 2, False)]
)
def test_shared_audio_must_obey_continuity_format_not_only_generic_audio_loader(
    tmp_path, rate, channels, accepted
):
    path = tmp_path / "synthetic.wav"
    path.write_bytes(synthetic_wav(rate=rate, channels=channels))
    if accepted:
        assert wav_duration(path)[0] == 2000  # Continuity uses recording-relative milliseconds.
    else:
        with pytest.raises(LandmarkError):
            wav_duration(path)


@pytest.mark.parametrize("offset", [-160, 139])
def test_normalized_shared_audio_accepts_signed_origin_and_rejects_offset_tampering(client, offset):
    created, auth, key = create(client, purpose="recovery")
    assert send_face(client, created, auth, sign(client, created, key)).status_code == 200
    voice = face_outcome(client, created, auth)
    assert voice["status"] == "voice_challenge"
    audio = ("voice.wav", synthetic_wav())
    # Opaque transport fixture: native MP4/AAC decoding is covered by Android instrumentation.
    video = ("voice.mp4", b"\x00\x00\x00\x18ftypmp42synthetic-shared-container")
    proof = sign(client, created, key, "voice", {"audio": audio, "video": video}, offset)

    def submit(received_offset):
        return client.post(
            f"/v1/sessions/{created['session_id']}/voice",
            headers=auth,
            data={
                "voice_challenge_id": voice["voice_challenge_id"],
                "media_signature": proof,
                "audio_offset_ms": str(received_offset),
            },
            files={"audio": audio, "video": video},
        )

    rejected = submit(offset + 1)
    assert rejected.status_code == 409
    assert rejected.json()["error_code"] == "media_not_accepted"
    accepted = submit(offset)
    assert accepted.status_code == 200 and accepted.json() == {"status": "pass"}
    with client.app.state.vericlue.transaction() as state:
        session = state.sessions.get(created["session_id"])
        assert session.voice_audio_offset_ms == offset
        assert session.audio.read_bytes() == audio[1]
        assert session.voice_video.read_bytes() == video[1]


@pytest.mark.parametrize("offset", [-5001, 5001])
def test_shared_audio_offset_remains_bounded_by_http_contract(client, offset):
    created, auth, key = create(client, purpose="recovery")
    assert send_face(client, created, auth, sign(client, created, key)).status_code == 200
    voice = face_outcome(client, created, auth)
    response = client.post(
        f"/v1/sessions/{created['session_id']}/voice",
        headers=auth,
        data={"voice_challenge_id": voice["voice_challenge_id"], "audio_offset_ms": str(offset)},
        files={"audio": ("voice.wav", synthetic_wav()), "video": ("voice.mp4", b"synthetic")},
    )
    assert response.status_code == 422
