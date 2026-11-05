"""Small helpers: unique slugs, read time and excerpts."""
import math
import re
import string
from typing import Optional, Type

from django.db import models
from django.utils.crypto import get_random_string
from django.utils.text import slugify

WORDS_PER_MINUTE = 200
EXCERPT_LENGTH = 200


def generate_unique_slug(
    model: Type[models.Model],
    value: str,
    instance_pk: Optional[int] = None,
    max_length: int = 255,
    fallback: str = "item",
) -> str:
    """
    Build a URL slug from `value` that is unique for `model`.

    If the plain slug is already taken, a short random suffix is appended
    (e.g. "my-post" -> "my-post-k3x9ab"), repeated until it is unique.
    """
    base = slugify(value)[: max_length - 7].strip("-") or fallback
    slug = base
    queryset = model.objects.all()
    if instance_pk is not None:
        queryset = queryset.exclude(pk=instance_pk)

    while queryset.filter(slug=slug).exists():
        suffix = get_random_string(6, allowed_chars=string.ascii_lowercase + string.digits)
        slug = f"{base}-{suffix}"
    return slug


def calculate_read_time(content: str) -> int:
    """Estimated reading time in whole minutes (200 words/min, minimum 1)."""
    words = len(content.split())
    return max(1, math.ceil(words / WORDS_PER_MINUTE))


def make_excerpt(content: str, length: int = EXCERPT_LENGTH) -> str:
    """First `length` characters of the content, cut at a word boundary."""
    text = re.sub(r"\s+", " ", content).strip()
    if len(text) <= length:
        return text
    cut = text[:length].rsplit(" ", 1)[0].rstrip(".,;:!?-")
    return f"{cut}..."
