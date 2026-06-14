"""
File Validator — валидация файлов по magic bytes (сигнатуре файла).

Проверяет реальный тип файла по первым байтам, а не по расширению или MIME.
Защита от инъекции через поддельный Content-Type.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Magic bytes signatures for supported file types
MAGIC_SIGNATURES = {
    "pdf": [b"%PDF"],
    "docx": [b"PK\x03\x04"],  # ZIP archive (DOCX is ZIP)
    "xlsx": [b"PK\x03\x04"],  # ZIP archive (XLSX is ZIP)
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "webp": [b"RIFF"],  # RIFF container, need to check "WEBP" at offset 8
    "txt": None,  # No magic bytes for text files
    "mp4": [b"\x00\x00\x00\x18ftyp", b"\x00\x00\x00\x1cftyp", b"\x00\x00\x00 ftyp"],
    "webm": [b"\x1a\x45\xdf\xa3"],
    "wav": [b"RIFF"],  # RIFF container, need to check "WAVE" at offset 8
    "mp3": [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3"],
    "m4a": [b"\x00\x00\x00\x20ftyp", b"\x00\x00\x00\x18ftyp"],
}

# Map allowed MIME types to expected magic signatures
MIME_TO_SIGNATURES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/msword": "docx",  # DOC is not ZIP but shares some patterns
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/gif": "gif",
    "image/webp": "webp",
    "text/plain": "txt",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mp4",
    "video/x-msvideo": "mp4",  # AVI has different signature, but mp4 fallback
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
}


def validate_file_magic(content: bytes, expected_mime: str) -> bool:
    """
    Validate file content matches expected MIME type via magic bytes.

    Args:
        content: First 32+ bytes of the file
        expected_mime: The MIME type claimed by the client

    Returns:
        True if magic bytes match or validation is inconclusive
    """
    if len(content) < 4:
        return False

    file_type = MIME_TO_SIGNATURES.get(expected_mime)
    if file_type is None:
        return True  # No signature to check (e.g., text/plain)

    signatures = MAGIC_SIGNATURES.get(file_type)
    if signatures is None:
        return True  # No known signature

    for sig in signatures:
        if content[:len(sig)] == sig:
            # Extra check for WebP (RIFF container)
            if file_type == "webp" and len(content) >= 12:
                if content[8:12] == b"WEBP":
                    return True
                continue
            # Extra check for WAV (RIFF container)
            if file_type == "wav" and len(content) >= 12:
                if content[8:12] == b"WAVE":
                    return True
                continue
            return True

    logger.warning(
        "[FileValidator] Magic bytes mismatch: expected %s (%s) but got %s",
        expected_mime, file_type, content[:8].hex(),
    )
    return False


def get_file_extension(content: bytes) -> Optional[str]:
    """Guess file extension from magic bytes."""
    if len(content) < 4:
        return None

    if content[:4] == b"%PDF":
        return ".pdf"
    if content[:4] == b"PK\x03\x04":
        return ".zip"  # Could be DOCX or XLSX
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if content[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if content[:4] == b"RIFF" and len(content) >= 12:
        if content[8:12] == b"WEBP":
            return ".webp"
        if content[8:12] == b"WAVE":
            return ".wav"
    if content[:3] == b"ID3" or content[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"

    return None
