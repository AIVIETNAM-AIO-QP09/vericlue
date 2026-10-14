"""Trạng thái trong bộ nhớ của một ứng dụng (TẠM — PLAT-05 thay bằng PostgreSQL).

Mỗi `create_app()` có kho riêng nên test không dùng chung dữ liệu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request

from vericlue_api.core.config import Settings
from vericlue_api.services.forensic_service import ForensicStore
from vericlue_api.services.review_store import ReviewStore
from vericlue_api.services.session_flow import SessionFlow
from vericlue_api.services.session_store import SessionStore


@dataclass
class AppState:
    settings: Settings
    sessions: SessionStore = field(default_factory=SessionStore)
    reviews: ReviewStore = field(default_factory=ReviewStore)
    forensic: ForensicStore = field(init=False)
    flow: SessionFlow = field(init=False)

    def __post_init__(self) -> None:
        self.forensic = ForensicStore(
            self.settings.provisional_threshold_b, self.settings.provisional_threshold_a
        )
        self.flow = SessionFlow(self.settings, self.sessions, self.reviews)
        if self.settings.use_mock_models:
            self.reviews.seed_demo()


def get_state(request: Request) -> AppState:
    return request.app.state.vericlue
