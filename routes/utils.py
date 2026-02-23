"""Utility functions for route handlers."""
from fastapi import UploadFile

# Re-export temp_file from services layer for backwards compatibility
from services.file_utils import temp_file  # noqa: F401


async def save_upload(upload: UploadFile, dest_path: str):
    """Save uploaded file to destination path."""
    content = await upload.read()
    with open(dest_path, "wb") as f:
        f.write(content)
