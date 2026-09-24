from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile
from io import BytesIO

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/octet-stream",
    "application/x-pdf",
}


def detect_resume_kind(data: bytes, filename: str, content_type: str | None) -> tuple[str, str]:
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")

    suffix = Path(filename or "resume").suffix.lower()
    mime = (content_type or "").split(";")[0].strip().lower()
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a PDF, DOCX, or TXT resume.",
        )
    if mime and mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a PDF, DOCX, or TXT resume.",
        )

    kind = None
    if data.startswith(b"%PDF"):
        kind = "pdf"
    elif data.startswith(b"PK"):
        try:
            with ZipFile(BytesIO(data)) as zf:
                names = [name.replace("\\", "/").lower() for name in zf.namelist()]
            if any(name.startswith("word/") for name in names) or "[content_types].xml" in names:
                kind = "docx"
        except BadZipFile as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded DOCX file is not valid.",
            ) from exc
    elif b"\x00" not in data[:4096]:
        try:
            data.decode("utf-8")
            kind = "txt"
        except UnicodeDecodeError:
            try:
                data.decode("latin-1")
                kind = "txt"
            except UnicodeDecodeError:
                kind = None

    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a PDF, DOCX, or TXT resume.",
        )

    expected = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}
    if suffix in expected and expected[suffix] != kind:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file contents do not match the file type. Please upload a PDF, DOCX, or TXT resume.",
        )
    if mime == "application/pdf" and kind != "pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file contents do not match the file type. Please upload a PDF, DOCX, or TXT resume.",
        )
    stored_suffix = {"pdf": ".pdf", "docx": ".docx", "txt": ".txt"}[kind]
    original = Path(filename or f"resume{stored_suffix}").name or f"resume{stored_suffix}"
    return original, stored_suffix


def _validated_resume(upload: UploadFile, data: bytes) -> tuple[str, str]:
    filename = upload.filename or "resume.pdf"
    suffix = Path(filename).suffix.lower()
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a PDF, DOCX, or TXT resume.",
        )
    return detect_resume_kind(data, filename, upload.content_type)


def save_resume_file(account_id: int, upload: UploadFile, data: bytes) -> tuple[Path, str, str]:
    settings = get_settings()
    filename, suffix = _validated_resume(upload, data)
    dest_dir = settings.upload_path / "resumes" / str(account_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = dest_dir / f"{uuid4().hex}{suffix}"
    mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }[suffix]
    return stored, filename, mime


def save_draft_resume(upload: UploadFile, data: bytes) -> tuple[Path, str, str]:
    settings = get_settings()
    filename, suffix = _validated_resume(upload, data)
    dest_dir = settings.upload_path / "drafts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = dest_dir / f"{uuid4().hex}{suffix}"
    mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }[suffix]
    return stored, filename, mime


PHOTO_TYPES = {
    "jpeg": ("image/jpeg", ".jpg"),
    "png": ("image/png", ".png"),
    "webp": ("image/webp", ".webp"),
}


def detect_photo_kind(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a JPG, PNG, or WebP photo.")


def save_profile_photo(account_id: int, data: bytes, *, prefix: str = "") -> tuple[Path, str]:
    settings = get_settings()
    kind = detect_photo_kind(data)
    mime, suffix = PHOTO_TYPES[kind]
    dest_dir = settings.upload_path / "photos" / str(account_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}{uuid4().hex}{suffix}" if prefix else f"{uuid4().hex}{suffix}"
    stored = dest_dir / name
    max_bytes = min(settings.max_upload_mb, 5) * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photo must be 5 MB or smaller.",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    stored.write_bytes(data)
    return stored, mime


def save_cover_photo(account_id: int, data: bytes) -> tuple[Path, str]:
    return save_profile_photo(account_id, data, prefix="cover-")


def save_perk_image(perk_id: int, data: bytes) -> tuple[Path, str]:
    settings = get_settings()
    kind = detect_photo_kind(data)
    mime, suffix = PHOTO_TYPES[kind]
    dest_dir = settings.upload_path / "perks"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = dest_dir / f"{perk_id}-{uuid4().hex}{suffix}"
    max_bytes = min(settings.max_upload_mb, 5) * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image must be 5 MB or smaller.",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    stored.write_bytes(data)
    return stored, mime


def assert_resume_size(data: bytes) -> None:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Resume must be {settings.max_upload_mb} MB or smaller.",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")


def write_bytes(path: Path, data: bytes) -> None:
    assert_resume_size(data)
    path.write_bytes(data)


def safe_download_name(name: str) -> str:
    cleaned = Path(name or "resume").name.replace('"', "").replace("\r", "").replace("\n", "")
    return cleaned or "resume"


def contained_upload_path(stored_path: str | Path | None) -> Path | None:
    """Return a resolved path only when it stays inside the upload root."""
    if not stored_path:
        return None
    try:
        path = Path(stored_path).resolve()
        root = get_settings().upload_path.resolve()
        path.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return path


def resolve_stored_file(stored_path: str | Path | None, *, missing_detail: str = "File not found.") -> Path:
    path = contained_upload_path(stored_path)
    if path is None or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)
    return path


def unlink_contained_file(stored_path: str | Path | None) -> None:
    path = contained_upload_path(stored_path)
    if path is None:
        return
    path.unlink(missing_ok=True)
