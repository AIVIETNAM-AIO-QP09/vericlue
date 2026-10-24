"""Local developer API. Bind to 127.0.0.1; not a public eKYC endpoint."""

import json
import os
from typing import Annotated, Literal

from face_matching import match_pair
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from identity_lab import MAX_BYTES, IdentityLab, InputError
from schemas import FacePairResult, MatchResult, OCRResult
from starlette.concurrency import run_in_threadpool

app = FastAPI(title="VeriClue Identity Lab (developer only)", version="0.1.0")
lab = IdentityLab()
legacy_face_lab = IdentityLab(face_model="adaface_ir18")
FACE_EMBEDDING_MODE = os.environ.get("FACE_EMBEDDING_MODE", "single")
if FACE_EMBEDDING_MODE not in {"single", "flip_mean"}:
    raise ValueError("Unsupported FACE_EMBEDDING_MODE")


async def image_bytes(upload: UploadFile) -> bytes:
    try:
        data = await upload.read(MAX_BYTES + 1)
    finally:
        await upload.close()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, detail="E_FILE_SIZE")
    return data


async def execute(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except InputError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except Exception as exc:
        # Do not send paths, data or model internals to clients.
        raise HTTPException(503, detail="E_MODEL_UNAVAILABLE") from exc


@app.get("/health")
def health():
    return {
        "status": "alive",
        "ocr_loaded": lab._ocr is not None,
        "face_loaded": lab._recognizer is not None,
        "production_ready": False,
    }


@app.post("/dev/v1/ocr", response_model=OCRResult)
async def ocr(image: Annotated[UploadFile, File()]):
    return await execute(lab.ocr, await image_bytes(image))


@app.post("/dev/v1/face-match", response_model=MatchResult)
async def match(reference: Annotated[UploadFile, File()], selfie: Annotated[UploadFile, File()]):
    return await execute(
        legacy_face_lab.match, await image_bytes(reference), await image_bytes(selfie)
    )


@app.post("/dev/v2/face-match", response_model=FacePairResult)
async def match_v2(
    reference: Annotated[UploadFile, File()],
    selfie: Annotated[UploadFile, File()],
    reference_roi: Annotated[
        str | None,
        Form(description="Optional JSON [x1,y1,x2,y2] portrait region after EXIF correction"),
    ] = None,
    embedding_mode: Annotated[Literal["single", "flip_mean"], Form()] = FACE_EMBEDDING_MODE,
):
    try:
        roi = json.loads(reference_roi) if reference_roi is not None else None
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, detail="E_REFERENCE_ROI") from exc
    return await execute(
        match_pair,
        lab,
        await image_bytes(reference),
        await image_bytes(selfie),
        None,
        roi,
        embedding_mode,
    )
