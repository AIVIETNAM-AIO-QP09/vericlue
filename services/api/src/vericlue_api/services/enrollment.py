"""Server-owned onboarding completion; templates stay outside sessions and HTTP."""

from __future__ import annotations

from collections.abc import Callable

from vericlue_api.services.accounts import AccountReceipt, AccountStore, unavailable
from vericlue_api.services.session_privacy import SessionPrivacy
from vericlue_api.services.session_store import Session
from vericlue_ml.common.detector import DetectorInput
from vericlue_ml.common.result import Module


class EnrollmentService:
    """Perform extraction and encrypted account creation in the caller's transaction."""

    def __init__(
        self,
        accounts: AccountStore,
        privacy: SessionPrivacy,
        extract_template: Callable,
        *,
        deadline: float | None = None,
    ) -> None:
        self.accounts = accounts
        self.privacy = privacy
        self.extract_template = extract_template
        self.deadline = deadline

    def complete(self, session: Session) -> AccountReceipt:
        """Use only server paths/evidence; failures roll back the surrounding decision."""
        self.accounts.validate_enrollment(session)
        if session.video is None or session.id_front is None or session.challenge.dynamic is None:
            raise unavailable()
        prepared, lease = self.privacy.prepare(
            session.session_id,
            {"video": session.video, "reference_image": session.id_front},
        )
        try:
            inp = DetectorInput(
                session_id=session.session_id,
                **prepared,
                metadata={
                    "expected_challenge": session.challenge.model_dump(
                        mode="json", exclude_none=True
                    )
                },
            )
            template = self.extract_template(
                inp,
                session.results[Module.FACE_MATCH],
                deadline=self.deadline,
                media_lease=lease,
            )
        finally:
            if lease is not None:
                lease.release()
        # Recheck gates, expiry, source hashes and nonce consumption after native work.
        return self.accounts.create(session, template)
