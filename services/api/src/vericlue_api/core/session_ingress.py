"""Authenticate session routes before FastAPI parses bodies; bound multipart while receiving.

Uses the official APIRoute hook. The small MultiPartParser subclass targets the
locked Starlette implementation; tests guard callback ordering and file cleanup.
No image type is inferred from the client filename: the image pipeline owns that.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from fastapi import Request, Response
from fastapi.routing import APIRoute
from python_multipart.multipart import parse_options_header
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData, Headers
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.responses import JSONResponse

from vericlue_api.core.errors import ApiError
from vericlue_api.core.security import preflight_session

MAX_PART_HEADER_BYTES = 8 * 1024
QR_MAX_BYTES = 16 * 1024
CHALLENGE_ID_MAX_BYTES = 256
SIGNATURE_MAX_BYTES = 160


@dataclass(frozen=True)
class MultipartRules:
    files: frozenset[str]
    fields: dict[str, int]


UPLOAD_RULES = {
    "upload_media": MultipartRules(
        frozenset({"image", "video"}),
        {"challenge_id": CHALLENGE_ID_MAX_BYTES, "media_signature": SIGNATURE_MAX_BYTES},
    ),
    "voice": MultipartRules(
        frozenset({"audio", "video"}),
        {
            "voice_challenge_id": CHALLENGE_ID_MAX_BYTES,
            "media_signature": SIGNATURE_MAX_BYTES,
            "audio_offset_ms": 8,
        },
    ),
    "upload_id_card": MultipartRules(frozenset({"front", "back"}), {"qr": QR_MAX_BYTES}),
}


class SessionMultipartParser(MultiPartParser):
    """Bound every part before writing chunks, including parts a handler would ignore."""

    def __init__(
        self,
        headers: Headers,
        stream: AsyncGenerator[bytes, None],
        *,
        rules: MultipartRules,
        max_file_bytes: int,
    ) -> None:
        super().__init__(
            headers,
            stream,
            max_files=len(rules.files),
            max_fields=len(rules.fields),
            max_part_size=max(rules.fields.values(), default=1),
        )
        self.rules = rules
        self.max_file_bytes = max_file_bytes
        self._seen: set[str] = set()
        self._part_bytes = 0
        self._header_bytes = 0
        self._ended = False

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._part_bytes = 0
        self._header_bytes = 0

    def _header_size(self, size: int) -> None:
        self._header_bytes += size
        if self._header_bytes > MAX_PART_HEADER_BYTES:
            raise MultiPartException("Part headers too large")

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._header_size(end - start)
        super().on_header_field(data, start, end)

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._header_size(end - start)
        super().on_header_value(data, start, end)

    def on_headers_finished(self) -> None:
        disposition, options = parse_options_header(self._current_part.content_disposition)
        try:
            name = options[b"name"].decode("ascii")
        except (KeyError, UnicodeError) as exc:
            raise MultiPartException("Invalid part name") from exc
        is_file = b"filename" in options
        allowed = self.rules.files if is_file else self.rules.fields
        if disposition != b"form-data" or name in self._seen or name not in allowed:
            raise MultiPartException("Unexpected or duplicate part")
        self._seen.add(name)
        # Validate role/count before the superclass allocates a temporary file.
        super().on_headers_finished()

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        self._part_bytes += end - start
        if self._current_part.file is not None:
            if self._part_bytes > self.max_file_bytes:
                raise ApiError(413, "upload_too_large", "File vượt quá giới hạn cho phép.")
        elif self._part_bytes > self.rules.fields[self._current_part.field_name]:
            raise ApiError(413, "request_too_large", "Dữ liệu gửi lên vượt quá giới hạn cho phép.")
        super().on_part_data(data, start, end)

    def on_end(self) -> None:
        self._ended = True
        super().on_end()

    async def parse(self) -> FormData:
        try:
            form = await super().parse()
            if not self._ended:
                raise MultiPartException("Incomplete multipart data")
            return form
        except BaseException:
            # Also close partial files when a truncated body has no closing boundary.
            for file in self._files_to_close_on_error:
                file.close()
            raise


class SessionAPIRoute(APIRoute):
    """Run short auth before body parsing; normal dependencies still recheck at use time."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()
        rules = UPLOAD_RULES.get(self.endpoint.__name__)

        async def secure(request: Request) -> Response:
            form = None
            try:
                try:
                    session_id = request.path_params.get("session_id")
                    if session_id is not None:
                        await run_in_threadpool(preflight_session, request, session_id)
                    if rules is not None:
                        media_type, _ = parse_options_header(
                            request.headers.get("content-type", "")
                        )
                        if media_type == b"multipart/form-data":
                            parser = SessionMultipartParser(
                                request.headers,
                                request.stream(),
                                rules=rules,
                                max_file_bytes=request.app.state.vericlue.settings.max_upload_mb
                                * 1024
                                * 1024,
                            )
                            try:
                                form = await parser.parse()
                            except MultiPartException as exc:
                                raise ApiError(
                                    400, "invalid_multipart", "Dữ liệu tải lên không hợp lệ."
                                ) from exc
                            # Request.form() in the original FastAPI handler reuses this
                            # cache instead of parsing (and spooling) the body twice.
                            request._form = form
                except ApiError as exc:
                    # No handler dependency transaction has begun yet. Do not catch
                    # original() errors: yield dependencies must see them and roll back.
                    return JSONResponse(
                        {"error_code": exc.error_code, "message": exc.message},
                        status_code=exc.status_code,
                        headers={"Cache-Control": "no-store"},
                    )
                return await original(request)
            finally:
                if form is not None:
                    await form.close()

        return secure
