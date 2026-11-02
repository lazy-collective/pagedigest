"""Shared atomic state and content-addressed body cache helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def empty_state() -> dict[str, Any]:
    return {
        "site_rev": None,
        "revs": {},
        "etag": None,
        "last_modified": None,
        "pages": {},
        "body_hashes": {},
        "manifest": None,
        "origin": None,
        "distrusted": False,
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("cache state must be a JSON object")

    site_rev = state.get("site_rev")
    revs = state.get("revs")
    pages = state.get("pages", {})
    if site_rev is not None and (type(site_rev) is not int or site_rev < 0):
        raise ValueError("cache state has an invalid site_rev")
    if not isinstance(revs, dict) or any(
        not isinstance(key, str) or type(value) is not int or value < 0 for key, value in revs.items()
    ):
        raise ValueError("cache state has an invalid rev map")
    if not isinstance(pages, dict) or any(
        not isinstance(key, str)
        or not isinstance(value, str)
        or len(value) != 69
        or not value.endswith(".body")
        or any(ch not in "0123456789abcdef" for ch in value[:-5])
        for key, value in pages.items()
    ):
        raise ValueError("cache state has an invalid page map")
    hashes = state.get("body_hashes", {})
    if not isinstance(hashes, dict) or any(
        not isinstance(key, str)
        or not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(ch not in "0123456789abcdef" for ch in value[7:])
        for key, value in hashes.items()
    ):
        raise ValueError("cache state has invalid body hashes")
    for field in ("etag", "last_modified"):
        if state.get(field) is not None and not isinstance(state[field], str):
            raise ValueError(f"cache state has an invalid {field}")
    return {**empty_state(), **state, "pages": pages}


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Atomically replace cache state after all required page fetches succeed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
            temp_name = temp.name
            json.dump(state, temp, indent=2, sort_keys=True)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)
