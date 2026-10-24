"""Reading timing uses fake emissions/streams only; no model, microphone or network."""

import hashlib
import json
import threading
from types import SimpleNamespace

import numpy as np
import pytest
from test_microphone_lab import fake_detector, finish_thread
from test_voice_align import VOCABULARY, ordinary

from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import ModuleResult
from vericlue_ml.eval.microphone import Recording
from vericlue_ml.eval.voice_trial import VoiceTrial
from vericlue_ml.voice import reading_timing as timing
from vericlue_ml.voice.align import Alignment, AlignmentError, ForcedAligner, SyllableSpan


class Backend:
    vocabulary = VOCABULARY
    model = None
    model_hashes = {}

    def __init__(self, gap=5):
        self.gap = gap
        self.inputs = []
        self.preloads = 0

    def preload(self, **kwargs):
        self.preloads += 1

    def emissions(self, samples):
        self.inputs.append(samples)
        return ordinary(self.gap), 0.02


def detector(monkeypatch, gap=5):
    # Presence checks may not trim the waveform sent to the aligner.
    monkeypatch.setattr(timing, "speech_bounds", lambda samples: (100, 200))
    backend = Backend(gap)
    return timing.ReadingTimingDetector(aligner=ForcedAligner(backend=backend)), backend


def test_ram_alignment_keeps_original_clock_and_model_cache(monkeypatch):
    model, backend = detector(monkeypatch)
    samples = np.full(32000, 0.1, np.float32)
    original = samples.copy()
    first = model.predict_samples(samples, 16000, prompt="Bà mẹ!")
    second = model.predict_samples(samples, 16000, prompt="bà mẹ")
    assert first.status == second.status == "degraded" and first.gate == "unclear"
    assert first.score is None and first.prob_attack is None
    assert not first.is_usable and backend.preloads == 1
    assert all(value is samples for value in backend.inputs)
    assert np.array_equal(samples, original)
    assert first.quality["syllables_per_second_including_gaps"] == pytest.approx(2 / 0.7)
    assert first.quality["longest_gap_seconds"] == pytest.approx(0.1)
    spans = next(e.value for e in first.evidence if e.name == "timing_syllables")
    assert spans[0] == {
        "text": "bà",
        "start_s": 0.1,
        "end_s": 0.4,
        "duration_s": pytest.approx(0.3),
    }
    assert model.provenance()["verified_model_hashes"] == {}


def test_long_pause_flags_do_not_become_a_splicing_or_acceptance_decision(monkeypatch):
    model, _ = detector(monkeypatch, gap=60)
    result = model.predict_samples(np.full(48000, 0.1, np.float32), 16000, prompt="bà mẹ")
    assert result.status == "degraded" and result.gate == "unclear"
    assert result.quality["longest_gap_seconds"] == pytest.approx(1.2)
    flags = next(e.value for e in result.evidence if e.name == "timing_flags")
    assert {row["kind"] for row in flags} >= {"long_pause", "long_star"}
    assert result.quality["timing_flag_count"] == len(flags)
    rules = next(e.value for e in result.evidence if e.name == "provisional_timing_rules")
    assert rules["validated"] is False and result.score is result.prob_attack is None


@pytest.mark.parametrize(
    "samples,rate",
    [
        (np.zeros(0, np.float32), 16000),
        (np.zeros(480001, np.float32), 16000),
        (np.zeros(16000, np.float64), 16000),
        (np.zeros((16000, 1), np.float32), 16000),
        (np.zeros(16000, np.float32), 8000),
        (np.zeros(16000, np.float32), 16000.0),
        (np.full(16000, np.nan, np.float32), 16000),
        (np.full(16000, 1.01, np.float32), 16000),
    ],
)
def test_bad_pcm_cannot_load_ctc(monkeypatch, samples, rate):
    model, backend = detector(monkeypatch)
    result = model.predict_samples(samples, rate, prompt="bà mẹ")
    assert result.status == "error" and result.error_code == "E_DECODE"
    assert not backend.inputs and not backend.preloads


@pytest.mark.parametrize("prompt", [None, "", "猫", "a" * 513])
def test_bad_prompt_cannot_decode_or_load(monkeypatch, tmp_path, prompt):
    model, backend = detector(monkeypatch)
    monkeypatch.setattr(
        timing, "load_audio", lambda *a, **kw: pytest.fail("bad prompt must fail first")
    )
    result = model.predict(
        DetectorInput(audio=tmp_path / "missing.wav", metadata={"prompt": prompt})
    )
    assert result.gate == "unclear" and not backend.inputs
    assert result.status == "degraded"


def test_silence_does_not_force_a_sentence_or_load_model(monkeypatch):
    from vericlue_ml.voice.asr import speech_bounds

    model, backend = detector(monkeypatch)
    monkeypatch.setattr(timing, "speech_bounds", speech_bounds)
    result = model.predict_samples(np.zeros(16000, np.float32), 16000, prompt="bà mẹ")
    assert result.status == "not_applicable" and result.gate == "unclear"
    assert not backend.inputs and not backend.preloads and result.evidence == []


def test_broken_backend_never_leaks_private_error(monkeypatch):
    model, backend = detector(monkeypatch)

    def broken(samples):
        raise RuntimeError("PRIVATE_MODEL_PATH")

    backend.emissions = broken
    result = model.predict_samples(np.full(32000, 0.1, np.float32), 16000, prompt="bà mẹ")
    assert result.status == "error" and result.gate == "unclear"
    assert "PRIVATE" not in json.dumps(result.to_contract())
    assert result.evidence == []


@pytest.mark.parametrize(
    "spans",
    [
        (SyllableSpan("bà", 0, 0.4), SyllableSpan("mẹ", 0.3, 0.8)),
        (SyllableSpan("bà", -0.1, 0.4), SyllableSpan("mẹ", 0.5, 0.8)),
        (SyllableSpan("bà", 0.1, float("nan")), SyllableSpan("mẹ", 0.5, 0.8)),
        (SyllableSpan("bà", 0.1, 0.4), SyllableSpan("mẹ", 0.5, 3.0)),
        (SyllableSpan("ba", 0.1, 0.4), SyllableSpan("me", 0.5, 0.8)),
    ],
)
def test_malformed_spans_are_not_reported(spans):
    with pytest.raises(AlignmentError):
        timing.timing_result(Alignment(spans, (), (), ()), "bà mẹ", 2)


def test_aligner_ram_input_is_checked_before_backend_work():
    model = ForcedAligner(backend=object())
    with pytest.raises(timing.DecodeError):
        model.align_samples(np.zeros(16000, np.float32), 48000, "bà mẹ")


def test_registry_timing_is_opt_in_cached_with_nonaccepting_mock(monkeypatch):
    from vericlue_ml.registry import get_detector, get_reading_timing

    get_reading_timing.cache_clear()
    result = get_reading_timing(mock=True).predict(DetectorInput())
    assert result.status == "degraded" and result.gate == "unclear"
    assert get_reading_timing() is get_reading_timing()
    assert (
        get_detector("voice_challenge", mock=False).__class__.__name__ == "VoiceChallengeDetector"
    )
    get_reading_timing.cache_clear()


@pytest.mark.parametrize("content_gate", ["pass", "fail"])
@pytest.mark.parametrize("timing_broken", [False, True])
def test_one_take_keeps_asr_and_spoof_independent_and_wipes_pcm(
    monkeypatch, content_gate, timing_broken
):
    from vericlue_ml.eval.voice_trial import nes2net_samples

    samples = np.full(96000, 0.1, np.float32)
    expected_hash = hashlib.sha256(
        nes2net_samples(samples, 48000).astype("<f4").tobytes()
    ).hexdigest()
    ctc, backend = detector(monkeypatch)
    qwen = fake_detector()
    qwen.predict_samples = lambda *a, **kw: ModuleResult(
        module="voice_challenge",
        model_version="unit-qwen",
        status="ok",
        gate=content_gate,
        latency_ms=1,
    )
    seen = []
    if timing_broken:

        def broken(*a, **kw):
            raise RuntimeError("PRIVATE_CTC")

        ctc.predict_samples = broken

    def spoof(pcm, *, cancelled):
        seen.append(pcm)
        return {"result": {"status": "degraded", "gate": "unclear", "score": 1.5}}

    trial = VoiceTrial(
        qwen,
        recorder=lambda *a, **kw: Recording(samples, 48000),
        spoof=SimpleNamespace(predict_samples=spoof),
        timing=ctc,
    )
    trial.start("bà mẹ")
    finish_thread(trial)
    events = trial.poll()
    body, error = events[-1][1]
    assert error is None and body["result"]["gate"] == content_gate
    assert body["voice_spoof"]["result"]["score"] == 1.5
    assert body["reading_timing"]["pcm_float32_sha256"] == expected_hash
    assert body["reading_timing"]["result"]["status"] == ("error" if timing_broken else "degraded")
    assert not samples.any() and not seen[0].any()
    if not timing_broken:
        assert backend.inputs[0] is seen[0]  # Same resampled PCM, no extra take or trim.
    assert [kind for kind, _ in events] == [
        "processing",
        "spoof_processing",
        "timing_processing",
        "done",
    ]
    assert "PRIVATE_CTC" not in json.dumps(body)


def test_cancel_during_ctc_discards_all_outputs_and_forbids_overlap(monkeypatch):
    samples = np.full(32000, 0.1, np.float32)
    entered, release = threading.Event(), threading.Event()
    ctc, _ = detector(monkeypatch)
    original = ctc.predict_samples

    def blocking(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    ctc.predict_samples = blocking
    trial = VoiceTrial(
        fake_detector(), recorder=lambda *a, **kw: Recording(samples, 16000), timing=ctc
    )
    trial.start("bà mẹ")
    assert entered.wait(5)
    trial.cancel()
    assert not trial.start("lượt mới")
    release.set()
    finish_thread(trial)
    assert trial.poll() == [("done", (None, None))]
    assert not samples.any() and not trial.active


def test_headless_render_names_forced_alignment_and_keeps_content_independent(monkeypatch):
    from vericlue_ml.eval.voice_lab import VoiceLab

    model, _ = detector(monkeypatch)
    result = model.predict_samples(np.full(32000, 0.1, np.float32), 16000, prompt="bà mẹ")
    lab = object.__new__(VoiceLab)
    seen = []
    lab._timing_result = seen.append
    lab.payload = {
        "result": {"status": "ok", "gate": "fail"},
        "reading_timing": {"result": result.to_contract()},
    }
    lab.render_timing()
    assert "MỐC ÉP CĂN" in seen[0] and "Câu chưa khớp" in seen[0]
    assert "bà: 0.10" in seen[0] and "gồm khoảng ngắt" in seen[0]
    lab.payload["reading_timing"]["result"].update(status="error", evidence=[])
    lab.render_timing()
    assert "CHƯA CĂN ĐƯỢC" in seen[1]


def test_cli_report_is_exclusive_and_drops_timing_if_audio_changes(monkeypatch, tmp_path):
    from vericlue_ml.eval import reading_timing as cli

    audio, text, output = (tmp_path / name for name in ("audio.wav", "prompt.txt", "report.json"))
    audio.write_bytes(b"unit-audio")
    text.write_text("bà mẹ", encoding="utf-8")

    class Fake:
        name, version = "voice_challenge", timing.VERSION

        def predict(self, inp):
            audio.write_bytes(b"changed-audio")
            return ModuleResult(
                module=self.name,
                model_version=self.version,
                status="degraded",
                gate="unclear",
                evidence=[],
                latency_ms=1,
            )

        def provenance(self):
            return {"model_version": self.version, "calibrated": False}

    monkeypatch.setattr(cli, "ReadingTimingDetector", lambda *a: Fake())
    args = [
        "--audio",
        str(audio),
        "--expected-text-file",
        str(text),
        "--models-dir",
        str(tmp_path / "models"),
        "--output",
        str(output),
    ]
    assert cli.main(args) == 1
    body = json.loads(output.read_text(encoding="utf-8"))
    assert body["result"]["error_code"] == "E_INTEGRITY"
    assert body["result"]["evidence"] == [] and body["sample_count"] == 1
    with pytest.raises(SystemExit):
        cli.main(args)


@pytest.mark.parametrize("target", ["audio.wav", "prompt.txt", "models/output.json"])
def test_cli_rejects_input_model_outputs_before_loading(monkeypatch, tmp_path, target):
    from vericlue_ml.eval import reading_timing as cli

    monkeypatch.setattr(
        cli, "ReadingTimingDetector", lambda *a: pytest.fail("must reject before load")
    )
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--audio",
                str(tmp_path / "audio.wav"),
                "--expected-text-file",
                str(tmp_path / "prompt.txt"),
                "--models-dir",
                str(tmp_path / "models"),
                "--output",
                str(tmp_path / target),
            ]
        )
