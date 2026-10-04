"""Utility helpers: hashing, slugification, token normalization."""

from __future__ import annotations

import hashlib
import re


def sha256_short(text: str, length: int = 12) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:length]


def slugify(text: str, max_length: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_length].rstrip("-") or "untitled"
