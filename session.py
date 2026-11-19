"""Isolated, process-owned temporary media directories."""

import atexit
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

SESSION_PATTERN = re.compile(r"session-[a-z0-9_]{8}\Z")


def is_redirect(path):
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except FileNotFoundError:
        return False


def remove_sessions(directory):
    for child in directory.iterdir():
        if not SESSION_PATTERN.fullmatch(child.name):
            continue
        if is_redirect(child) or not child.is_dir():
            raise RuntimeError(f"Unexpected temporary session entry: {child}")
        shutil.rmtree(child)


def start_session(installation):
    import msvcrt

    temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
    key = hashlib.sha256(os.fsencode(os.path.normcase(str(installation)))).hexdigest()[:16]
    directory = temporary_root / f"TemporatorWan2GP-{key}"
    directory.mkdir(exist_ok=True)
    if is_redirect(directory):
        raise RuntimeError(f"Temporary session directory is redirected: {directory}")
    lock_path = directory / "active.lock"
    if is_redirect(lock_path):
        raise RuntimeError(f"Temporary session lock is redirected: {lock_path}")
    lock = lock_path.open("a+b")
    try:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except PermissionError as exc:
            raise RuntimeError("Another Temporator instance is using this Wan2GP installation") from exc
        remove_sessions(directory)
        session = Path(tempfile.mkdtemp(prefix="session-", dir=directory))
    except BaseException:
        lock.close()
        raise

    def cleanup():
        try:
            remove_sessions(directory)
        finally:
            lock.close()

    return session, cleanup


def open_temporary_session(installation):
    directory, cleanup = start_session(installation)
    original_tempdir = tempfile.tempdir
    keys = ("TEMP", "TMP", "TMPDIR", "GRADIO_TEMP_DIR")
    previous = {key: os.environ.get(key) for key in keys}

    def close():
        tempfile.tempdir = original_tempdir
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cleanup()

    try:
        temporary = directory / "temp"
        gradio = directory / "gradio"
        temporary.mkdir()
        gradio.mkdir()
        os.environ.update(dict.fromkeys(keys[:3], str(temporary)))
        os.environ["GRADIO_TEMP_DIR"] = str(gradio)
        tempfile.tempdir = str(temporary)
    except BaseException:
        close()
        raise
    atexit.register(close)
    return directory

