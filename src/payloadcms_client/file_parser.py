"""Utilities for parsing article documents with YAML front matter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import re

import yaml

_FRONT_MATTER_PATTERN = re.compile(
    r"^---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


@dataclass(slots=True)
class ArticleDocument:
    """Represents an article document with metadata and HTML body."""

    metadata: Dict[str, Any]
    body: str
    raw: str

    @property
    def slug(self) -> str | None:
        """Return the slug if it exists in the metadata, otherwise ``None``."""

        value = self.metadata.get("slug")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None


def parse_article_file(file_path: str | Path) -> ArticleDocument:
    """Parse an HTML article document that contains YAML front matter.

    Parameters
    ----------
    file_path:
        Path to the article document. The file is expected to begin with a YAML
        front matter block delimited by ``---`` lines, followed by the HTML
        content.

    Returns
    -------
    ArticleDocument
        The parsed document including metadata, HTML body, and the raw
        contents.

    Raises
    ------
    ValueError
        If the file does not include YAML front matter or if the front matter
        cannot be parsed as a mapping.
    """

    path = Path(file_path)
    text = path.read_text(encoding="utf-8")

    stripped = text.lstrip("\ufeff")
    match = _FRONT_MATTER_PATTERN.match(stripped)
    if not match:
        raise ValueError(
            f"File '{path}' does not contain YAML front matter delimited by '---' lines."
        )

    metadata_text = match.group("meta").strip()
    body = match.group("body")

    try:
        metadata = yaml.safe_load(metadata_text) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"Failed to parse YAML front matter in '{path}': {exc}") from exc

    if not isinstance(metadata, dict):
        raise ValueError(
            f"Front matter in '{path}' must be a YAML mapping, got: {type(metadata).__name__}."
        )

    return ArticleDocument(metadata=metadata, body=body, raw=text)
