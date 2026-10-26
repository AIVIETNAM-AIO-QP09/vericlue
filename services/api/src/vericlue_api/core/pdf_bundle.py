"""Canonical JSON + exact PDF signatures, verified against caller-pinned keys only."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import stat
import struct
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from vericlue_api.core.signing import public_key_fingerprint, verify
from vericlue_api.schemas.forensic import PdfReportManifest

DOMAIN = b"vericlue-forensic-pdf-bundle-v1\x00"
MAX_PDF_BYTES = 32 * 1024 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ZIP_BYTES = MAX_PDF_BYTES + MAX_JSON_BYTES + 4096
MEMBERS = {"report.pdf": MAX_PDF_BYTES, "report.json": MAX_JSON_BYTES, "report.sig": 160}


def canonical_manifest(manifest: PdfReportManifest) -> bytes:
    """Protocol v1 serialization; no NaN, omitted None fields, or alternate key ordering."""
    raw = json.dumps(
        manifest.model_dump(mode="json", exclude_none=True),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    checked = PdfReportManifest.model_validate_json(raw)
    normalized = json.dumps(
        checked.model_dump(mode="json", exclude_none=True),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    if normalized != raw:
        raise ValueError("Noncanonical manifest")
    if not 0 < len(raw) <= MAX_JSON_BYTES or manifest.job.status != "done":
        raise ValueError("Report manifest unavailable")
    return raw


def signing_message(raw: bytes, key_id: str) -> bytes:
    """Domain/fingerprint supplied by the trusted signing or verification key."""
    return DOMAIN + key_id.encode("ascii") + b"\x00" + raw


def make_archive(pdf: bytes, raw: bytes, signature: str) -> bytes:
    """Fixed flat member names, without compression or private key material."""
    if not pdf.startswith(b"%PDF-") or not 0 < len(pdf) <= MAX_PDF_BYTES:
        raise ValueError("PDF unavailable")
    if not 0 < len(raw) <= MAX_JSON_BYTES or len(signature) != 88:
        raise ValueError("Manifest unavailable")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in (
            ("report.pdf", pdf),
            ("report.json", raw),
            ("report.sig", signature.encode("ascii")),
        ):
            archive.writestr(name, data)
    return output.getvalue()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def verify_parts(
    pdf: bytes,
    raw: bytes,
    signature: str,
    key: Ed25519PublicKey,
    *,
    expected_job_id: str | None = None,
) -> PdfReportManifest:
    """Check signature before parsing JSON, then exact PDF hash and requested job."""
    try:
        if not isinstance(key, Ed25519PublicKey) or not 0 < len(raw) <= MAX_JSON_BYTES:
            raise ValueError("Invalid input bounds")
        if (
            not pdf.startswith(b"%PDF-")
            or not 0 < len(pdf) <= MAX_PDF_BYTES
            or len(signature) != 88
        ):
            raise ValueError("Invalid PDF/signature")
        decoded = base64.b64decode(signature, validate=True)
        if len(decoded) != 64 or base64.b64encode(decoded).decode("ascii") != signature:
            raise ValueError("Invalid signature encoding")
        fingerprint = public_key_fingerprint(key)
        if not verify(signing_message(raw, fingerprint), decoded, key):
            raise ValueError("Invalid signature")
        parsed = json.loads(raw.decode("ascii"), object_pairs_hook=_unique_object)
        manifest = PdfReportManifest.model_validate(parsed)
        if canonical_manifest(manifest) != raw or manifest.key_id != fingerprint:
            raise ValueError("Invalid manifest encoding/key")
        if manifest.pdf_sha256 != hashlib.sha256(pdf).hexdigest():
            raise ValueError("PDF changed")
        if expected_job_id is not None and manifest.job.job_id != expected_job_id:
            raise ValueError("Wrong report subject")
        return manifest
    except Exception as exc:
        raise ValueError("Bundle not verified") from exc


def verify_archive(
    raw_zip: bytes, key: Ed25519PublicKey, *, expected_job_id: str | None = None
) -> PdfReportManifest:
    """Read bounded, fixed ZIP members without extracting or rendering any files."""
    try:
        if not 0 < len(raw_zip) <= MAX_ZIP_BYTES:
            raise ValueError("Archive bounds")
        # Only our small, three-member, single-disk archive format. Bound the
        # central directory before ZipFile materializes its entries in memory.
        if len(raw_zip) < 22 or raw_zip[-22:-18] != b"PK\x05\x06":
            raise ValueError("Archive directory unavailable")
        _, disk, directory_disk, count_disk, count, directory_size, offset, comment = struct.unpack(
            "<4s4H2LH", raw_zip[-22:]
        )
        if (
            disk != 0
            or directory_disk != 0
            or count_disk != 3
            or count != 3
            or comment != 0
            or directory_size > 4096
            or offset + directory_size != len(raw_zip) - 22
        ):
            raise ValueError("Archive directory bounds")
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            infos = archive.infolist()
            if len(infos) != 3 or {info.filename for info in infos} != set(MEMBERS):
                raise ValueError("Unexpected/duplicate members")
            parts = {}
            for info in infos:
                limit = MEMBERS[info.filename]
                if (
                    info.compress_type != zipfile.ZIP_STORED
                    or info.flag_bits & 1
                    or info.is_dir()
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or not 0 < info.file_size <= limit
                ):
                    raise ValueError("Unsafe archive member")
                with archive.open(info) as handle:
                    content = handle.read(limit + 1)
                if not 0 < len(content) <= limit:
                    raise ValueError("Archive member bounds")
                parts[info.filename] = content
        return verify_parts(
            parts["report.pdf"],
            parts["report.json"],
            parts["report.sig"].decode("ascii"),
            key,
            expected_job_id=expected_job_id,
        )
    except Exception as exc:
        raise ValueError("Bundle not verified") from exc
