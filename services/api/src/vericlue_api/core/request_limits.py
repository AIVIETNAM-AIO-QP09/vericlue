"""Bound incoming bodies and session creation for the single-process demo API."""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
from collections import deque
from collections.abc import Callable
from ipaddress import ip_address
from threading import Lock
from time import monotonic

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from vericlue_api.core.config import Settings

CREDENTIAL_BODY_MAX_BYTES = 8 * 1024


class RequestLimitError(HTTPException):
    """An HTTP exception that also survives FastAPI's body-parsing boundary."""

    def __init__(self) -> None:
        super().__init__(413, "Dữ liệu gửi lên vượt quá giới hạn cho phép.")


class SessionCreationLimiter:
    """Atomic sliding window, bounded memory, no raw client addresses retained."""

    def __init__(
        self, limit: int, window: int, max_clients: int, *, clock: Callable[[], float] = monotonic
    ) -> None:
        self.limit = limit
        self.window = window
        self.max_clients = max_clients
        self.clock = clock
        self._key = secrets.token_bytes(32)
        self._entries: dict[bytes, deque[float]] = {}
        self._lock = Lock()

    def check(self, host: str) -> int | None:
        """Reserve an attempt; return retry seconds, or fail closed when cache is full."""
        try:
            address = ip_address(host)
            if address.version == 6 and address.ipv4_mapped is not None:
                address = address.ipv4_mapped
            host = str(address)
        except ValueError:
            # ASGI test transports and Unix sockets may use a non-IP peer name.
            pass
        key = hmac.digest(self._key, host.encode("utf-8"), hashlib.sha256)
        with self._lock:
            now = self.clock()
            cutoff = now - self.window
            entries = self._entries.get(key)
            if entries is None:
                if len(self._entries) >= self.max_clients:
                    expired = [k for k, v in self._entries.items() if v[-1] <= cutoff]
                    for stale in expired:
                        del self._entries[stale]
                if len(self._entries) >= self.max_clients:
                    raise OverflowError("Session rate capacity reached")
                entries = self._entries[key] = deque()
            while entries and entries[0] <= cutoff:
                entries.popleft()
            if len(entries) >= self.limit:
                return max(1, math.ceil(entries[0] + self.window - now))
            entries.append(now)
        return None


class RequestLimitsMiddleware:
    """Check headers before parsing; count actual bytes before passing each chunk."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.max_bytes = settings.max_request_mb * 1024 * 1024
        self.sessions = SessionCreationLimiter(
            settings.session_create_limit,
            settings.session_create_window_seconds,
            settings.session_rate_max_clients,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        lengths = [v for k, v in scope["headers"] if k.lower() == b"content-length"]
        if lengths:
            value = lengths[0]
            if (
                len(lengths) != 1
                or not 1 <= len(value) <= 20
                or not value.isdigit()
                or any(k.lower() == b"transfer-encoding" for k, _ in scope["headers"])
            ):
                await self._reject(scope, receive, send, 400, "invalid_content_length")
                return
            if int(value) > self.max_bytes:
                await self._reject(scope, receive, send, 413, "request_too_large")
                return

        path = scope["path"]
        root = scope.get("root_path", "")
        if root and (path == root or path.startswith(root + "/")):
            path = path[len(root) :]
        # Verifier requests are small JSON; bound bytes before body parsing/crypto.
        limit = (
            min(self.max_bytes, CREDENTIAL_BODY_MAX_BYTES)
            if path == "/v1/credentials" or path.startswith("/v1/credentials/")
            else self.max_bytes
        )
        if lengths and int(lengths[0]) > limit:
            await self._reject(scope, receive, send, 413, "request_too_large")
            return

        if scope["method"] == "POST" and path == "/v1/sessions":
            peer = scope.get("client")
            if not peer or not peer[0]:
                await self._reject(scope, receive, send, 503, "rate_limit_unavailable")
                return
            try:
                retry = self.sessions.check(peer[0])
            except OverflowError:
                await self._reject(scope, receive, send, 503, "rate_limit_unavailable")
                return
            if retry is not None:
                await self._reject(scope, receive, send, 429, "session_rate_limited", retry=retry)
                return

        total = 0

        async def limited_receive() -> Message:
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > limit:
                    raise RequestLimitError()
            return message

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        status: int,
        code: str,
        *,
        retry: int | None = None,
    ) -> None:
        message = {
            400: "Thông tin yêu cầu không hợp lệ.",
            413: "Dữ liệu gửi lên vượt quá giới hạn cho phép.",
            429: "Bạn đã tạo nhiều phiên xác minh. Vui lòng thử lại sau.",
            503: "Dịch vụ xác thực đang bận. Vui lòng thử lại sau.",
        }[status]
        headers = {"Cache-Control": "no-store"}
        if retry is not None:
            headers["Retry-After"] = str(retry)
        await JSONResponse(
            {"error_code": code, "message": message}, status_code=status, headers=headers
        )(scope, receive, send)
