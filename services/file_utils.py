"""File utility functions for services layer."""
import os
import tempfile
from contextlib import contextmanager


@contextmanager
def temp_file(suffix: str):
    """Context manager for temporary files with automatic cleanup."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)
