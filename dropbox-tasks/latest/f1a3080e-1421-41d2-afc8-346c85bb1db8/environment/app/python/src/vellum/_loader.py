"""Load the bundled native library and expose thin call wrappers."""

from __future__ import annotations

import ctypes
import os

_LIB = None


def _library_path() -> str:
    override = os.environ.get("VELLUM_NATIVE")
    if override:
        return override
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "libvellum.so")


def _lib() -> ctypes.CDLL:
    global _LIB
    if _LIB is None:
        lib = ctypes.CDLL(_library_path())
        lib.vellum_identity_json.restype = ctypes.c_void_p
        lib.vellum_canonical_digest.argtypes = [ctypes.c_char_p]
        lib.vellum_canonical_digest.restype = ctypes.c_void_p
        lib.vellum_free.argtypes = [ctypes.c_void_p]
        lib.vellum_free.restype = None
        _LIB = lib
    return _LIB


def _take(ptr) -> str | None:
    if not ptr:
        return None
    try:
        return ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8")
    finally:
        _lib().vellum_free(ptr)


def identity_json() -> str:
    ptr = _lib().vellum_identity_json()
    text = _take(ptr)
    if text is None:
        raise RuntimeError("vellum: native identity unavailable")
    return text


def canonical_digest(document_json: str) -> str:
    ptr = _lib().vellum_canonical_digest(document_json.encode("utf-8"))
    text = _take(ptr)
    if text is None:
        raise ValueError("vellum: document could not be canonicalized")
    return text
