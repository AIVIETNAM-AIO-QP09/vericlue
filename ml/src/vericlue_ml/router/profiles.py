"""Explicit module groups for ADR-0012; full preserves the original pipeline."""

from dataclasses import dataclass
from typing import Literal

from vericlue_ml.common.result import Module

RouterProfileName = Literal["full", "mvp"]
FACE_MODULES = (Module.FACE_PAD, Module.FACE_DEEPFAKE)


@dataclass(frozen=True)
class RouterProfile:
    name: RouterProfileName
    presence_modules: tuple[Module, ...]
    voice_modules: tuple[Module, ...]
    advisory_voice_modules: tuple[Module, ...] = ()

    @property
    def finalize_modules(self) -> tuple[Module, ...]:
        return (Module.QUALITY, *FACE_MODULES, *self.presence_modules)

    @property
    def voice_step_modules(self) -> tuple[Module, ...]:
        return (*self.required_voice_step_modules, *self.advisory_voice_modules)

    @property
    def required_voice_step_modules(self) -> tuple[Module, ...]:
        return (Module.VOICE_CHALLENGE, *self.voice_modules)

    @property
    def calibration_modules(self) -> frozenset[Module]:
        return frozenset((*FACE_MODULES, *self.voice_modules))

    @property
    def modules(self) -> tuple[Module, ...]:
        # LIVE-02 is a standalone diagnostic until all dynamic gates are integrated.
        # Adding its enum must not change legacy model loading, health or pass policy.
        return (
            tuple(module for module in Module if module != Module.GAZE_TRACKING)
            if self.name == "full"
            else (*self.finalize_modules, *self.voice_step_modules)
        )


def get_profile(name: RouterProfileName = "full") -> RouterProfile:
    """Reject unknown profiles instead of silently selecting a weaker policy."""
    if name == "full":
        return RouterProfile(
            name, (Module.CHROMAPULSE, Module.CAMPROBE), (Module.VOICE_SPOOF, Module.LIPSYNC)
        )
    if name == "mvp":
        return RouterProfile(name, (Module.CAMPROBE,), (Module.VOICE_SPOOF,), (Module.LIPSYNC,))
    raise ValueError(f"Unknown router profile: {name}")
