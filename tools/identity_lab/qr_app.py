"""Private loopback QR/portrait bridge. No OCR or image/text logging."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from qr_scanner import MAX_BYTES, CardScanner, InputError
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartParser

MultiPartParser.spool_max_size = MAX_BYTES + 1
scanner = CardScanner()


@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(scanner.preload)
    yield


app = FastAPI(title="VeriClue QR bridge", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "qr_only",
        "ocr_enabled": False,
        "portrait_loaded": scanner._finder is not None,
    }


async def image_bytes(upload):
    try:
        data = await upload.read(MAX_BYTES + 1)
    finally:
        await upload.close()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, detail="E_FILE_SIZE")
    return data


@app.post("/internal/id-card")
async def scan_card(
    front: Annotated[UploadFile, File()], back: Annotated[UploadFile | None, File()] = None
):
    front_data = await image_bytes(front)
    back_data = await image_bytes(back) if back is not None else None
    try:
        return await run_in_threadpool(scanner.scan, front_data, back_data)
    except InputError as exc:
        raise HTTPException(422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(503, detail="E_QR_UNAVAILABLE") from None
