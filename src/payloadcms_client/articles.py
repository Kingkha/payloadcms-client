"""Helpers for building Payload CMS article payloads."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Mapping, Sequence, Tuple
import re
import unicodedata

from .file_parser import ArticleDocument, parse_article_file

if TYPE_CHECKING:  # pragma: no cover
    from .payload_client import PayloadRESTClient

_SLUG_INVALID_RE = re.compile(r"[^a-z0-9-]+")


def slugify(value: str) -> str:
    """Convert ``value`` into a URL-friendly slug."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    hyphenated = _SLUG_INVALID_RE.sub("-", lowered)
    cleaned = hyphenated.strip("-")
    cleaned = re.sub(r"-+", "-", cleaned)
    if not cleaned:
        raise ValueError("Slug cannot be derived from an empty string.")
    return cleaned


def _slugify_path(value: str) -> str:
    """Slugify each component in ``value`` and join them using ``/``."""

    parts = [part for part in re.split(r"[\\/]+", value) if part]
    if not parts:
        return ""
    slug_parts = [slugify(part) for part in parts]
    return "/".join(slug_parts)


@dataclass(slots=True)
class ArticlePayloadBuilder:
    """Builds request payloads for creating or updating articles.
    
    Parameters
    ----------
    slug_field : str
        Field name for the article slug. Default: "slug"
    body_field : str
        Field name for the article body content. Default: "content"
    defaults : Mapping[str, Any]
        Default field values to include in every payload. Default: {}
    convert_to_lexical : bool
        If True, converts HTML to Lexical editor format. If False (default),
        stores raw HTML. Use False for simpler setup with a text/textarea/code
        field, then render with dangerouslySetInnerHTML on frontend. Default: False
    """

    slug_field: str = "slug"
    body_field: str = "content"
    defaults: Mapping[str, Any] = field(default_factory=dict)
    convert_to_lexical: bool = False

    def build(self, document: ArticleDocument) -> Tuple[str, Dict[str, Any]]:
        """Return a ``(slug, payload)`` tuple for the provided document."""

        if not isinstance(document.metadata, Mapping):
            raise TypeError("document.metadata must be a mapping")

        payload: Dict[str, Any] = {**self.defaults, **document.metadata}

        slug_value = payload.get(self.slug_field)
        if isinstance(slug_value, str) and slug_value.strip():
            slug = slug_value.strip()
        else:
            title = payload.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ValueError(
                    "Cannot infer slug: front matter must include either a slug or a title."
                )
            slug = slugify(title.strip())
            payload[self.slug_field] = slug

        body_content = document.body.strip()
        
        if self.convert_to_lexical:
            # Convert HTML to Lexical editor format (more complex)
            from .html_to_lexical import html_to_lexical
            payload[self.body_field] = html_to_lexical(body_content)
        else:
            # Store raw HTML (simpler approach - recommended)
            payload[self.body_field] = body_content

        return slug, payload


def _prepare_media_payload(defaults: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not defaults:
        return {}
    return dict(defaults)


def _resolve_featured_image_path(
    value: str,
    article_path: Path,
    media_root: str | Path | None,
) -> Path:
    candidate = Path(value)
    if candidate.is_file():
        return candidate

    cleaned = value.lstrip("/\\")
    search_paths = []
    if media_root is not None:
        search_paths.append(Path(media_root))
    search_paths.append(article_path.parent)

    for base in search_paths:
        resolved = base / cleaned
        if resolved.is_file():
            return resolved

    raise FileNotFoundError(
        f"Unable to locate featured image '{value}' relative to '{article_path}'."
    )


def _ensure_featured_image(
    client: "PayloadRESTClient",
    *,
    featured_value: Any,
    article_path: Path,
    media_collection: str,
    media_root: str | Path | None,
    media_defaults: Mapping[str, Any] | None,
    filename_field: str,
    depth: int | None,
) -> Any:
    if not isinstance(featured_value, str) or not featured_value.strip():
        return featured_value

    resolved_path = _resolve_featured_image_path(featured_value.strip(), article_path, media_root)

    existing = client.find_first_by_field(
        media_collection,
        filename_field,
        resolved_path.name,
        depth=depth,
    )
    if existing:
        if isinstance(existing, Mapping) and "doc" in existing and isinstance(existing["doc"], Mapping):
            existing = existing["doc"]
        if not isinstance(existing, Mapping):
            raise TypeError(
                "Media lookup must return a mapping-compatible document."
            )
        media_id = existing.get("id")
        if media_id is None:
            raise ValueError(
                f"Existing media document for '{resolved_path.name}' is missing an 'id'."
            )
        return media_id

    payload = _prepare_media_payload(media_defaults)
    document = client.upload_media(
        media_collection,
        resolved_path,
        data=payload,
        depth=depth,
    )
    if isinstance(document, Mapping) and "doc" in document and isinstance(document["doc"], Mapping):
        document = document["doc"]
    if not isinstance(document, Mapping):
        raise TypeError("Media upload must return a mapping-compatible document.")
    media_id = document.get("id")
    if media_id is None:
        raise ValueError(
            f"Uploaded media document for '{resolved_path.name}' is missing an 'id'."
        )
    return media_id


def upload_article_from_file(
    client: "PayloadRESTClient",
    collection: str,
    file_path: str,
    *,
    builder: ArticlePayloadBuilder | None = None,
    depth: int | None = None,
    featured_image_field: str = "featuredImage",
    media_collection: str = "media",
    media_root: str | Path | None = None,
    media_defaults: Mapping[str, Any] | None = None,
    media_filename_field: str = "filename",
    media_depth: int | None = None,
    slug_prefix: str | None = None,
) -> Dict[str, Any]:
    """Parse an article file and upsert it into Payload CMS.

    Parameters
    ----------
    client:
        Configured :class:`~payload_client.PayloadRESTClient` instance.
    collection:
        Name of the collection to upload the article to.
    file_path:
        Path to the HTML file that contains the YAML front matter and body.
    builder:
        Optional :class:`ArticlePayloadBuilder` to customise slug/body handling.
    depth:
        Optional depth parameter for Payload REST queries when fetching existing
        documents.
    featured_image_field:
        Name of the field within the payload that stores the featured image
        relationship. If the field is present and set to a string path, the
        referenced file is uploaded to the media collection and the field is
        replaced with the uploaded document ID. Pass ``None`` to disable
        automatic media handling.
    media_collection:
        Payload collection name used for storing media uploads. Defaults to
        ``"media"``.
    media_root:
        Optional directory used to resolve relative featured image paths. When
        provided, paths are first searched relative to this directory before
        falling back to the article file's parent directory.
    media_defaults:
        Optional mapping of additional form fields submitted with each media
        upload (for example, ``{"alt": "Article cover"}``).
    media_filename_field:
        Field name queried when attempting to reuse an existing media document
        based on the local file name. Defaults to ``"filename"``.
    media_depth:
        Optional depth parameter for media lookups or uploads.
    slug_prefix:
        Optional slug prefix applied to the computed slug before upserting the
        article. Each component separated by ``/`` is slugified and prepended to
        the generated slug. Existing slugs that already begin with the prefix
        are left unchanged.

    Returns
    -------
    dict
        The JSON response from the Payload CMS REST API.
    """

    article_path = Path(file_path)
    builder = builder or ArticlePayloadBuilder()
    document = parse_article_file(article_path)
    slug, payload = builder.build(document)

    if slug_prefix:
        normalized_prefix = _slugify_path(slug_prefix)
        if normalized_prefix and not slug.startswith(f"{normalized_prefix}/") and slug != normalized_prefix:
            slug = f"{normalized_prefix}/{slug.lstrip('/')}"
            payload[builder.slug_field] = slug

    if featured_image_field and featured_image_field in payload:
        payload[featured_image_field] = _ensure_featured_image(
            client,
            featured_value=payload[featured_image_field],
            article_path=article_path,
            media_collection=media_collection,
            media_root=media_root,
            media_defaults=media_defaults,
            filename_field=media_filename_field,
            depth=media_depth,
        )

    return client.upsert_by_field(
        collection=collection,
        field=builder.slug_field,
        value=slug,
        payload=payload,
        depth=depth,
    )


def upload_articles_from_directory(
    client: "PayloadRESTClient",
    collection: str,
    directory: str | Path,
    *,
    pattern: str = "*.html",
    recursive: bool = True,
    builder: ArticlePayloadBuilder | None = None,
    depth: int | None = None,
    featured_image_field: str = "featuredImage",
    media_collection: str = "media",
    media_root: str | Path | None = None,
    media_defaults: Mapping[str, Any] | None = None,
    media_filename_field: str = "filename",
    media_depth: int | None = None,
) -> List[Dict[str, Any]]:
    """Upload article files from ``directory`` using folder names as slug prefixes.

    Parameters
    ----------
    directory:
        Directory that contains article documents with YAML front matter. Files
        are discovered using ``Path.glob`` and sorted for deterministic
        processing.
    pattern:
        Glob pattern used to match files. Defaults to ``"*.html"``.
    recursive:
        When ``True`` (default), search recursively using ``**/``. Set to
        ``False`` to only consider files directly within ``directory``.
    """

    root = Path(directory)
    if not root.is_dir():
        raise ValueError(
            f"Directory '{directory}' does not exist or is not a directory."
        )

    glob_pattern = f"**/{pattern}" if recursive else pattern
    files = sorted(path for path in root.glob(glob_pattern) if path.is_file())

    results: List[Dict[str, Any]] = []
    for path in files:
        relative = path.relative_to(root)
        slug_prefix = None
        if relative.parent != Path("."):
            slug_prefix = relative.parent.as_posix()

        response = upload_article_from_file(
            client=client,
            collection=collection,
            file_path=str(path),
            builder=builder,
            depth=depth,
            featured_image_field=featured_image_field,
            media_collection=media_collection,
            media_root=media_root,
            media_defaults=media_defaults,
            media_filename_field=media_filename_field,
            media_depth=media_depth,
            slug_prefix=slug_prefix,
        )
        results.append(response)

    return results


def ensure_categories(
    client: "PayloadRESTClient",
    categories: Sequence[str] | Iterable[str],
    *,
    collection: str = "categories",
    slug_field: str = "slug",
    label_field: str = "title",
    defaults: Mapping[str, Any] | None = None,
    depth: int | None = None,
) -> List[Dict[str, Any]]:
    """Ensure that each category exists in Payload CMS.

    Parameters
    ----------
    client:
        Configured :class:`~payload_client.PayloadRESTClient` instance.
    categories:
        Iterable of category labels. Each label is slugified and used to upsert a
        document within the ``collection``.
    collection:
        The name of the Payload CMS collection that stores categories.
    slug_field:
        Field name used for the category slug. Defaults to ``"slug"``.
    label_field:
        Field name used for the human-readable category label/title. Defaults to
        ``"title"``.
    defaults:
        Optional mapping of default fields merged into each category payload.
    depth:
        Optional depth parameter passed to Payload CMS when checking for
        existing documents.

    Returns
    -------
    list of dict
        The JSON documents returned from the Payload REST API for each
        processed category, preserving the order of first appearance in the
        input iterable (deduplicated by slug).
    """

    if defaults is None:
        defaults = {}

    unique_categories: "OrderedDict[str, str]" = OrderedDict()
    for name in categories:
        if not isinstance(name, str):
            raise TypeError("Category names must be strings.")
        label = name.strip()
        if not label:
            raise ValueError("Category names cannot be empty or whitespace.")
        slug = slugify(label)
        unique_categories.setdefault(slug, label)

    results: List[Dict[str, Any]] = []
    for slug, label in unique_categories.items():
        payload: Dict[str, Any] = {**defaults, slug_field: slug, label_field: label}
        document = client.upsert_by_field(
            collection=collection,
            field=slug_field,
            value=slug,
            payload=payload,
            depth=depth,
        )
        results.append(document)

    return results
