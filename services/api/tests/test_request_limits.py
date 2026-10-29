"""Resource limits must run before parsing, database work or session allocation."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from synthetic_images import synthetic_image

from vericlue_api.core.config import Settings, get_settings
from vericlue_api.core.request_limits import RequestLimitsMiddleware, SessionCreationLimiter
from vericlue_api.main import create_app


def test_default_limit_and_validation():
    settings = Settings(_env_file=None, session_create_limit=3)
    assert settings.session_create_window_seconds == 3600
    for values in (
        {"session_create_limit": 0},
        {"session_create_window_seconds": 0},
        {"session_rate_max_clients": 0},
        {"max_request_mb": 0},
        {"max_upload_mb": 0},
    ):
        with pytest.raises(ValueError):
            Settings(_env_file=None, **values)


def test_sliding_window_not_reset_by_rejections():
    clock = [0.0]
    limiter = SessionCreationLimiter(3, 3600, 10, clock=lambda: clock[0])
    assert limiter.check("192.0.2.1") is None
    clock[0] = 100
    assert limiter.check("192.0.2.1") is None
    clock[0] = 200
    assert limiter.check("192.0.2.1") is None
    assert limiter.check("192.0.2.1") == 3400
    clock[0] = 3599.1
    assert limiter.check("192.0.2.1") == 1
    clock[0] = 3600
    assert limiter.check("192.0.2.1") is None
    assert limiter.check("192.0.2.1") == 100


def test_capacity_cannot_evict_live_clients_and_bypass_limit():
    clock = [0.0]
    limiter = SessionCreationLimiter(1, 60, 1, clock=lambda: clock[0])
    assert limiter.check("192.0.2.1") is None
    with pytest.raises(OverflowError):
        limiter.check("192.0.2.2")
    assert limiter.check("192.0.2.1") == 60
    clock[0] = 60
    assert limiter.check("192.0.2.2") is None
    assert len(limiter._entries) == 1
    assert all(isinstance(key, bytes) and len(key) == 32 for key in limiter._entries)


def test_ipv6_notation_and_ipv4_mapped_addresses_share_quota():
    limiter = SessionCreationLimiter(1, 60, 10)
    assert limiter.check("2001:db8::1") is None
    assert limiter.check("2001:0db8:0:0:0:0:0:1") is not None
    assert limiter.check("192.0.2.1") is None
    assert limiter.check("::ffff:192.0.2.1") is not None


def test_concurrent_reservations_cannot_exceed_quota():
    limiter = SessionCreationLimiter(3, 3600, 10)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: limiter.check("192.0.2.1"), range(50)))
    assert sum(result is None for result in results) == 3


def test_http_fourth_session_rejected_but_existing_session_still_works(monkeypatch):
    monkeypatch.setenv("SESSION_CREATE_LIMIT", "3")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        sessions = [client.post("/v1/sessions") for _ in range(3)]
        assert [r.status_code for r in sessions] == [200, 200, 200]
        session = sessions[0].json()
        response = client.post("/v1/sessions")
        assert response.status_code == 429
        assert response.json()["error_code"] == "session_rate_limited"
        assert set(response.json()) == {"error_code", "message"}
        assert 1 <= int(response.headers["Retry-After"]) <= 3600
        assert response.headers["Cache-Control"] == "no-store"
        assert client.get("/healthz").status_code == 200
        assert (
            client.post(
                f"/v1/sessions/{session['session_id']}/finalize",
                headers={"Authorization": f"Bearer {session['token']}"},
            ).status_code
            == 200
        )


def test_forwarded_headers_do_not_reset_peer_quota(monkeypatch):
    monkeypatch.setenv("SESSION_CREATE_LIMIT", "1")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        assert client.post("/v1/sessions").status_code == 200
        for headers in (
            {"X-Forwarded-For": "192.0.2.2"},
            {"CF-Connecting-IP": "192.0.2.3"},
            {"Forwarded": "for=192.0.2.4"},
        ):
            assert client.post("/v1/sessions", headers=headers).status_code == 429


def test_cors_allows_reading_retry_after_and_preflight_does_not_consume_quota(monkeypatch):
    monkeypatch.setenv("SESSION_CREATE_LIMIT", "1")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        origin = {"Origin": "http://localhost:3000"}
        assert (
            client.options(
                "/v1/sessions", headers={**origin, "Access-Control-Request-Method": "POST"}
            ).status_code
            == 200
        )
        assert client.post("/v1/sessions", headers=origin).status_code == 200
        response = client.post("/v1/sessions", headers=origin)
        assert response.status_code == 429
        assert response.headers["access-control-allow-origin"] == origin["Origin"]
        assert "Retry-After" in response.headers["access-control-expose-headers"]


def test_root_path_and_trailing_slash_cannot_bypass_quota(monkeypatch):
    monkeypatch.setenv("SESSION_CREATE_LIMIT", "1")
    get_settings.cache_clear()
    with TestClient(create_app(), root_path="/gateway") as client:
        assert client.post("/gateway/v1/sessions").status_code == 200
        assert client.post("/gateway/v1/sessions").status_code == 429
        assert client.post("/gateway/v1/sessions/").status_code == 429


def test_invalid_json_consumes_an_attempt_without_creating_a_session(monkeypatch):
    monkeypatch.setenv("SESSION_CREATE_LIMIT", "1")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        assert (
            client.post(
                "/v1/sessions", content=b"{", headers={"Content-Type": "application/json"}
            ).status_code
            == 422
        )
        assert client.post("/v1/sessions").status_code == 429


def test_different_peer_addresses_have_independent_quotas(monkeypatch):
    monkeypatch.setenv("SESSION_CREATE_LIMIT", "1")
    get_settings.cache_clear()
    app = create_app()

    async def run():
        for host in ("192.0.2.1", "192.0.2.2"):
            transport = httpx.ASGITransport(app=app, client=(host, 12345))
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                assert (await client.post("/v1/sessions")).status_code == 200
                assert (await client.post("/v1/sessions")).status_code == 429

    try:
        asyncio.run(run())
    finally:
        app.state.vericlue.orchestrator.close()
        app.state.vericlue.database.dispose()


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ([(b"content-length", b"1048577")], 413),
        ([(b"content-length", b"-1")], 400),
        ([(b"content-length", b"+1")], 400),
        ([(b"content-length", b"1,1")], 400),
        ([(b"content-length", b"9" * 1000)], 400),
        ([(b"content-length", b"1"), (b"Content-Length", b"1")], 400),
        ([(b"content-length", b"1"), (b"transfer-encoding", b"chunked")], 400),
    ],
)
def test_invalid_or_oversized_headers_never_read_body_or_enter_app(headers, status):
    async def forbidden(*_):
        pytest.fail("Rejected headers must not read the stream or invoke the app")

    messages = []

    async def send(message):
        messages.append(message)

    app = RequestLimitsMiddleware(forbidden, Settings(_env_file=None, max_request_mb=1))
    asyncio.run(app({"type": "http", "headers": headers}, forbidden, send))
    assert messages[0]["status"] == status


@pytest.mark.parametrize("peer", [None, ("", 123)])
def test_missing_peer_fails_closed(peer):
    async def forbidden(*_):
        pytest.fail("Missing peer must not enter app or read the body")

    messages = []

    async def send(message):
        messages.append(message)

    app = RequestLimitsMiddleware(forbidden, Settings(_env_file=None))
    asyncio.run(
        app(
            {
                "type": "http",
                "headers": [],
                "method": "POST",
                "path": "/v1/sessions",
                "client": peer,
            },
            forbidden,
            send,
        )
    )
    assert messages[0]["status"] == 503


def test_body_exactly_at_limit_is_accepted():
    async def downstream(scope, receive, send):
        sizes = []
        while True:
            message = await receive()
            sizes.append(len(message.get("body", b"")))
            if not message.get("more_body", False):
                break
        assert sum(sizes) == 1024 * 1024
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def chunks():
        yield b"x" * (512 * 1024)
        yield b"x" * (512 * 1024)

    async def run():
        app = RequestLimitsMiddleware(downstream, Settings(_env_file=None, max_request_mb=1))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/payload", content=chunks(), headers={"Content-Length": str(1024 * 1024)}
            )
            assert response.status_code == 204

    asyncio.run(run())


def test_streamed_multipart_stops_at_limit_closes_files_and_leaves_session_unchanged(
    monkeypatch,
):
    from starlette import formparsers

    monkeypatch.setenv("MAX_REQUEST_MB", "1")
    get_settings.cache_clear()
    opened = []
    factory = formparsers.SpooledTemporaryFile

    def tracked(*args, **kwargs):
        file = factory(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", tracked)
    with TestClient(create_app()) as sync:
        session = sync.post("/v1/sessions").json()
        sid = session["session_id"]
        auth = {"Authorization": f"Bearer {session['token']}"}

        async def chunks():
            yield (
                b'--boundary\r\nContent-Disposition: form-data; name="image"; '
                b'filename="face.jpg"\r\nContent-Type: image/jpeg\r\n\r\n' + b"x" * (600 * 1024)
            )
            yield (
                b'\r\n--boundary\r\nContent-Disposition: form-data; name="video"; '
                b'filename="face.mp4"\r\nContent-Type: video/mp4\r\n\r\n' + b"x" * (200 * 1024)
            )
            # Both files individually fit 1 MiB; their combined body does not.
            yield b"x" * (300 * 1024)
            pytest.fail("Middleware must stop receiving after the oversized chunk")

        async def run():
            transport = httpx.ASGITransport(app=sync.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/v1/sessions/{sid}/media",
                    content=chunks(),
                    headers={**auth, "Content-Type": "multipart/form-data; boundary=boundary"},
                )
                assert response.status_code == 413, response.text
                assert response.json()["error_code"] == "request_too_large"
                assert response.headers["Cache-Control"] == "no-store"

        asyncio.run(run())
        assert len(opened) == 2 and all(file.closed for file in opened)
        assert (
            sync.post(
                f"/v1/sessions/{sid}/media",
                headers=auth,
                files={"image": ("face.jpg", synthetic_image(b"\xff\xd8\xff"), "image/jpeg")},
            ).status_code
            == 200
        )


@pytest.mark.parametrize("declared_length", [None, "1"])
def test_json_stream_limit_uses_actual_bytes_even_if_length_missing_or_wrong(
    monkeypatch,
    declared_length,
):
    monkeypatch.setenv("MAX_REQUEST_MB", "1")
    get_settings.cache_clear()
    app = create_app()

    async def chunks():
        yield b" " * (700 * 1024)
        yield b" " * (400 * 1024)

    async def run():
        headers = {"Content-Type": "application/json"}
        if declared_length is not None:
            headers["Content-Length"] = declared_length
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/v1/sessions", headers=headers, content=chunks())
            assert response.status_code == 413, response.text
            assert response.json()["error_code"] == "request_too_large"

    asyncio.run(run())
    assert not app.state.vericlue._initialized


def test_http_capacity_rejection_is_503_not_an_unlimited_new_bucket(monkeypatch):
    monkeypatch.setenv("SESSION_CREATE_LIMIT", "1")
    monkeypatch.setenv("SESSION_RATE_MAX_CLIENTS", "1")
    get_settings.cache_clear()
    app = create_app()

    async def run():
        for host, expected in (("192.0.2.1", 200), ("192.0.2.2", 503), ("192.0.2.1", 429)):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, client=(host, 12345)), base_url="http://test"
            ) as client:
                response = await client.post("/v1/sessions")
                assert response.status_code == expected
                if expected == 503:
                    assert response.json()["error_code"] == "rate_limit_unavailable"

    try:
        asyncio.run(run())
    finally:
        app.state.vericlue.orchestrator.close()
        app.state.vericlue.database.dispose()
