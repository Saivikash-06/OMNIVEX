import hashlib
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Optional, Union
from backend.app.core.errors import SecurityViolationError


def verify_api_key_constant_time(provided_key: Optional[str], expected_key: Optional[str]) -> bool:
    """Constant-time comparison for API keys."""
    if expected_key is None:
        return True
    if provided_key is None:
        return False
    return secrets.compare_digest(provided_key, expected_key)


def sanitize_display_filename(name: str, max_length: int = 100) -> str:
    """Sanitize original client filename for safe display in metadata."""
    clean = re.sub(r'[^\w\s\.-]', '_', name)
    clean = clean.strip()
    if not clean:
        clean = "dataset.csv"
    if len(clean) > max_length:
        clean = clean[:max_length]
    return clean


def generate_safe_filename(suffix: str = ".csv") -> str:
    """Generate server-controlled UUID4 filename."""
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    return f"{uuid.uuid4().hex}{suffix}"


def resolve_safe_path(base_dir: Union[str, Path], filename: str) -> Path:
    """Resolve and verify that a filename stays strictly inside base_dir to prevent path traversal."""
    base = Path(base_dir).resolve()
    # Reject path components inside filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise SecurityViolationError("Path traversal or illegal filename characters detected.")
    
    target = (base / filename).resolve()
    try:
        common = Path(os.path.commonpath([str(base), str(target)]))
        if common != base:
            raise SecurityViolationError("Target path escapes designated storage directory.")
    except ValueError:
        raise SecurityViolationError("Target path is outside allowed storage volume.")
    return target


def compute_sha256(file_path: Union[str, Path]) -> str:
    """Compute SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def verify_file_hash(file_path: Union[str, Path], expected_hash: str) -> bool:
    """Verify that file content strictly matches expected SHA-256 hash."""
    actual_hash = compute_sha256(file_path)
    return secrets.compare_digest(actual_hash.lower(), expected_hash.lower())


def sanitize_formula_injection(value: str) -> str:
    """Neutralize spreadsheet formula injection by prepending a single quote

    if the string starts with '=', '+', '-', '@', tab, or carriage return.
    """
    if not value or not isinstance(value, str):
        return value
    if value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{value}"
    return value
