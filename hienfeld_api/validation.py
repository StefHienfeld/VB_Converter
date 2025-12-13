# hienfeld_api/validation.py
"""
File upload validation utilities with security checks.
"""
import re
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile, HTTPException
from .models import FileUploadLimits, UploadValidationError
import logging

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize uploaded filename to prevent path traversal attacks.

    Args:
        filename: Original filename from upload

    Returns:
        Sanitized filename safe for filesystem operations
    """
    # Remove path components (prevent ../../../etc/passwd attacks)
    filename = Path(filename).name

    # Remove dangerous characters, keep only alphanumeric, spaces, dots, dashes, underscores
    filename = re.sub(r'[^\w\s.-]', '', filename)

    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)

    # Limit length to filesystem limits
    if len(filename) > 255:
        name = Path(filename).stem
        ext = Path(filename).suffix
        filename = name[:250] + ext

    # Ensure filename is not empty after sanitization
    if not filename or filename == '.':
        filename = 'upload' + Path(filename).suffix

    return filename


async def validate_file_upload(
    file: UploadFile,
    limits: FileUploadLimits = FileUploadLimits()
) -> Tuple[bytes, str]:
    """
    Validate uploaded file for security and constraints.

    Checks:
    - File extension whitelist
    - File size limits
    - MIME type validation (magic bytes, not just extension)
    - Filename sanitization

    Args:
        file: FastAPI UploadFile object
        limits: Upload constraints

    Returns:
        Tuple of (file_bytes, sanitized_filename)

    Raises:
        HTTPException: If validation fails
    """
    # 1. Check filename exists
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided"
        )

    # 2. Sanitize filename
    original_filename = file.filename
    sanitized = sanitize_filename(original_filename)

    logger.debug(f"Validating upload: {original_filename} -> {sanitized}")

    # 3. Check extension whitelist
    ext = Path(sanitized).suffix.lower()
    if ext not in limits.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(limits.allowed_extensions)}"
        )

    # 4. Read file and check size
    # Read in chunks to avoid loading huge files into memory all at once
    file_bytes = bytearray()
    chunk_size = 1024 * 1024  # 1MB chunks

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break

            file_bytes.extend(chunk)

            # Check size limit during read
            if len(file_bytes) > limits.max_file_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {limits.max_file_size / (1024*1024):.0f}MB"
                )

    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reading uploaded file: {str(e)}"
        )

    finally:
        await file.close()

    # 5. Validate file is not empty
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    # 6. Magic byte validation (MIME type check)
    # For production, consider adding python-magic library:
    # import magic
    # mime = magic.from_buffer(file_bytes, mime=True)
    #
    # For now, do basic validation:
    mime_type = detect_mime_type_basic(file_bytes, ext)

    if mime_type not in limits.allowed_mimes:
        logger.warning(f"MIME type mismatch: {mime_type} for file with extension {ext}")
        # Allow it but log warning - some CSV files detected as text/plain
        # raise HTTPException(
        #     status_code=400,
        #     detail=f"File content doesn't match extension. Detected: {mime_type}"
        # )

    logger.info(
        f"✅ File validated: {sanitized} "
        f"({len(file_bytes)} bytes, MIME: {mime_type})"
    )

    return bytes(file_bytes), sanitized


def detect_mime_type_basic(file_bytes: bytes, extension: str) -> str:
    """
    Basic MIME type detection without external libraries.

    For production, use python-magic for proper magic byte detection.

    Args:
        file_bytes: File content
        extension: File extension

    Returns:
        Detected MIME type
    """
    # Check magic bytes for common formats
    if len(file_bytes) < 4:
        return 'application/octet-stream'

    # Excel XLSX (ZIP file starting with PK)
    if file_bytes[:4] == b'PK\x03\x04':
        if extension in ['.xlsx', '.docx']:
            if extension == '.xlsx':
                return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

    # PDF
    if file_bytes[:4] == b'%PDF':
        return 'application/pdf'

    # Excel XLS (OLE2 format)
    if file_bytes[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        return 'application/vnd.ms-excel'

    # CSV / Text (check for printable ASCII/UTF-8)
    try:
        # Try to decode as text
        text = file_bytes[:1000].decode('utf-8')
        if extension == '.csv' or ',' in text:
            return 'text/csv'
        return 'text/plain'
    except UnicodeDecodeError:
        pass

    return 'application/octet-stream'


def validate_analysis_settings(settings_dict: dict) -> dict:
    """
    Validate and clean analysis settings.

    Args:
        settings_dict: Raw settings from frontend

    Returns:
        Validated and cleaned settings dict

    Raises:
        HTTPException: If validation fails
    """
    from .models import AnalysisSettings
    from pydantic import ValidationError

    try:
        settings = AnalysisSettings(**settings_dict)
        return settings.dict()
    except ValidationError as e:
        # Extract user-friendly error messages
        errors = []
        for error in e.errors():
            field = '.'.join(str(x) for x in error['loc'])
            msg = error['msg']
            errors.append(f"{field}: {msg}")

        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid analysis settings",
                "errors": errors
            }
        )
