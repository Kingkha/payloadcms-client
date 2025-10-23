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
        
        # Ensure author/authors and editor from defaults override metadata if they're numeric IDs
        # (metadata might have string values like "Editor" which should be replaced with user IDs)
        for field in ['author', 'authors', 'editor']:
            if field in self.defaults:
                default_value = self.defaults[field]
                # Check if it's a numeric ID or list of numeric IDs
                if isinstance(default_value, int):
                    payload[field] = default_value
                elif isinstance(default_value, str) and default_value.isdigit():
                    payload[field] = default_value
                elif isinstance(default_value, list):
                    # For arrays like authors: [1, 2, 3]
                    payload[field] = default_value
        
        # Remove singular 'author' field if 'authors' (plural) is set
        # This avoids confusion when metadata has 'author' as a string
        if 'authors' in payload and 'author' in payload:
            del payload['author']

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


def _text_to_lexical(text: str) -> Dict[str, Any]:
    """Convert plain text to Lexical editor format (for caption field)."""
    return {
        "root": {
            "type": "root",
            "format": "",
            "indent": 0,
            "version": 1,
            "children": [
                {
                    "type": "paragraph",
                    "format": "",
                    "indent": 0,
                    "version": 1,
                    "children": [
                        {
                            "mode": "normal",
                            "text": text,
                            "type": "text",
                            "style": "",
                            "detail": 0,
                            "format": 0,
                            "version": 1,
                        }
                    ],
                    "direction": None,
                    "textFormat": 0,
                    "textStyle": "",
                }
            ],
            "direction": None,
        }
    }


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
    article_payload: Dict[str, Any] | None = None,
    featured_image_field: str = "featuredImage",
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

    # Prepare upload payload and alt/caption separately
    # Payload CMS requires alt/caption to be set via update after upload
    upload_payload = {}
    alt_caption_payload = {}
    
    # Separate alt/caption from other defaults
    if media_defaults:
        for key, value in media_defaults.items():
            if key.lower() in ("alt", "caption"):
                alt_caption_payload[key.lower()] = value
            else:
                upload_payload[key] = value
    
    # Extract companion fields from article payload (alt, caption, etc.)
    if article_payload:
        companion_fields = ["alt", "caption", "Alt", "Caption"]
        for suffix in companion_fields:
            companion_key = f"{featured_image_field}{suffix}"
            if companion_key in article_payload:
                # Use lowercase field names for media (standard convention)
                media_field = suffix.lower()
                alt_caption_payload[media_field] = article_payload[companion_key]
    
    # If alt or caption are still missing, use the filename as fallback
    if "alt" not in alt_caption_payload or not alt_caption_payload["alt"]:
        # Remove extension and convert underscores/hyphens to spaces
        filename_without_ext = resolved_path.stem
        readable_name = filename_without_ext.replace("-", " ").replace("_", " ")
        # Capitalize first letter of each word
        alt_caption_payload["alt"] = readable_name.title()
    
    if "caption" not in alt_caption_payload or not alt_caption_payload["caption"]:
        # Use the same readable filename for caption
        filename_without_ext = resolved_path.stem
        readable_name = filename_without_ext.replace("-", " ").replace("_", " ")
        alt_caption_payload["caption"] = readable_name.title()
    
    # Step 1: Upload the media file
    document = client.upload_media(
        media_collection,
        resolved_path,
        data=upload_payload if upload_payload else None,
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
    
    # Step 2: Update with alt and caption fields
    # Payload CMS requires this as a separate step - it doesn't accept these in multipart upload
    if alt_caption_payload:
        from .payload_client import PayloadRESTClient
        if isinstance(client, PayloadRESTClient):
            # Convert caption to Lexical format if it's a plain string
            # (Payload CMS media schemas often use richText for caption)
            if "caption" in alt_caption_payload and isinstance(alt_caption_payload["caption"], str):
                alt_caption_payload["caption"] = _text_to_lexical(alt_caption_payload["caption"])
            
            client.update_document(
                collection=media_collection,
                doc_id=media_id,
                payload=alt_caption_payload,
                depth=depth,
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
    featured_image_output_field: str | None = None,
    media_collection: str = "media",
    media_root: str | Path | None = None,
    media_defaults: Mapping[str, Any] | None = None,
    media_filename_field: str = "filename",
    media_depth: int | None = None,
    slug_prefix: str | None = None,
    category_field: str | None = None,
    category_output_field: str | None = None,
    category_collection: str = "categories",
    category_slug_field: str = "slug",
    category_label_field: str = "title",
    category_parent_field: str | None = None,
    category_skip_first: int = 0,
    category_defaults: Mapping[str, Any] | None = None,
    category_depth: int | None = None,
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
        replaced with the uploaded document ID. Companion fields (e.g.,
        ``featuredImageAlt``, ``featuredImageCaption``) are automatically
        extracted from the article payload and transferred to the media document,
        then removed from the article. If companion fields are not provided, the
        image filename (cleaned and formatted) is used as a fallback for both
        ``alt`` and ``caption``. Pass ``None`` to disable automatic media handling.
    featured_image_output_field:
        Optional name to rename the featured image field to after processing.
        Useful when your article YAML uses one field name (e.g. 'featuredImage')
        but your PayloadCMS schema expects a different name (e.g. 'heroImage').
        If None, keeps the original field name.
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
    category_field:
        Name of the field within the payload that contains category/tag values.
        If present and the field value is a list of strings, each category name
        is ensured to exist in the ``category_collection``, and the field is
        replaced with a list of category IDs. Pass ``None`` to disable automatic
        category handling. Common values: ``"tags"``, ``"categories"``.
    category_output_field:
        Optional name to rename the category field to after processing. Useful
        when your article YAML uses one field name (e.g. 'tags') but your
        PayloadCMS schema expects a different name (e.g. 'categories'). If None,
        keeps the original field name.
    category_collection:
        Payload collection name used for storing categories/tags. Defaults to
        ``"categories"``.
    category_slug_field:
        Field name used for the category slug. Defaults to ``"slug"``.
    category_label_field:
        Field name used for the category label/title. Defaults to ``"title"``.
    category_parent_field:
        Field name for parent relationship in category documents. If provided,
        enables hierarchical category support where tag at index
        ``category_skip_first + 1`` becomes a child of tag at index
        ``category_skip_first``. For example, with ``skip_first=2``, tag[2]
        (country) becomes parent of tag[3] (city). Pass ``None`` to disable.
        Default: ``None``.
    category_skip_first:
        Number of tags to skip from the beginning of the tag list before
        processing hierarchical relationships. For example, set to 2 to skip
        generic tags like "Travel" and "Guide". Default: 0.
    category_defaults:
        Optional mapping of default fields merged into each category payload.
    category_depth:
        Optional depth parameter for category lookups or creation.

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
        # Generate slug from filename (without extension)
        filename_slug = slugify(article_path.stem)
        # Use hyphen instead of slash since PayloadCMS doesn't support nested slugs
        slug = f"{normalized_prefix}-{filename_slug}"
        payload[builder.slug_field] = slug

    # Handle categories/tags if specified
    if category_field and category_field in payload:
        category_value = payload[category_field]
        if isinstance(category_value, (list, tuple)):
            # Extract string values only
            category_names = [
                item for item in category_value if isinstance(item, str)
            ]
            if category_names:
                # Handle hierarchical categories if parent field is specified
                if category_parent_field and len(category_names) > category_skip_first + 1:
                    # Process parent category first (country)
                    parent_index = category_skip_first
                    parent_name = category_names[parent_index]
                    
                    # Create/fetch parent category
                    parent_docs = ensure_categories(
                        client,
                        [parent_name],
                        collection=category_collection,
                        slug_field=category_slug_field,
                        label_field=category_label_field,
                        defaults=category_defaults,
                        depth=category_depth,
                    )
                    
                    # Get parent ID
                    parent_doc = parent_docs[0]
                    if isinstance(parent_doc, Mapping) and "doc" in parent_doc:
                        parent_doc = parent_doc["doc"]
                    parent_id = parent_doc.get("id") if isinstance(parent_doc, Mapping) else None
                    
                    # Process child category (city) with parent relationship
                    child_index = category_skip_first + 1
                    child_name = category_names[child_index]
                    
                    # Add parent to defaults for child category
                    child_defaults = dict(category_defaults or {})
                    if parent_id:
                        child_defaults[category_parent_field] = parent_id
                    
                    child_docs = ensure_categories(
                        client,
                        [child_name],
                        collection=category_collection,
                        slug_field=category_slug_field,
                        label_field=category_label_field,
                        defaults=child_defaults,
                        depth=category_depth,
                    )
                    
                    # Process remaining categories (after parent and child)
                    remaining_names = category_names[category_skip_first + 2:]
                    if remaining_names:
                        remaining_docs = ensure_categories(
                            client,
                            remaining_names,
                            collection=category_collection,
                            slug_field=category_slug_field,
                            label_field=category_label_field,
                            defaults=category_defaults,
                            depth=category_depth,
                        )
                        # Combine: parent + child + remaining (skipped tags are excluded)
                        category_docs = parent_docs + child_docs + remaining_docs
                    else:
                        category_docs = parent_docs + child_docs
                else:
                    # No hierarchy - process all categories normally
                    category_docs = ensure_categories(
                        client,
                        category_names,
                        collection=category_collection,
                        slug_field=category_slug_field,
                        label_field=category_label_field,
                        defaults=category_defaults,
                        depth=category_depth,
                    )
                
                # Extract IDs from the returned documents
                category_ids = []
                for doc in category_docs:
                    # Handle wrapped response (doc in doc)
                    if isinstance(doc, Mapping) and "doc" in doc and isinstance(doc["doc"], Mapping):
                        doc = doc["doc"]
                    if isinstance(doc, Mapping):
                        doc_id = doc.get("id")
                        if doc_id is not None:
                            category_ids.append(doc_id)
                # Replace the string values with IDs
                # If output field is different, remove old field and use new one
                if category_output_field and category_output_field != category_field:
                    del payload[category_field]
                    payload[category_output_field] = category_ids
                else:
                    payload[category_field] = category_ids

    if featured_image_field and featured_image_field in payload:
        media_id = _ensure_featured_image(
            client,
            featured_value=payload[featured_image_field],
            article_path=article_path,
            media_collection=media_collection,
            media_root=media_root,
            media_defaults=media_defaults,
            filename_field=media_filename_field,
            depth=media_depth,
            article_payload=payload,
            featured_image_field=featured_image_field,
        )
        
        # Remove companion fields from article payload after they've been transferred to media
        companion_fields = ["alt", "caption", "Alt", "Caption"]
        for suffix in companion_fields:
            companion_key = f"{featured_image_field}{suffix}"
            if companion_key in payload:
                del payload[companion_key]
        
        # If output field is different, remove old field and use new one
        if featured_image_output_field and featured_image_output_field != featured_image_field:
            del payload[featured_image_field]
            payload[featured_image_output_field] = media_id
        else:
            payload[featured_image_field] = media_id

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
    category_field: str | None = None,
    category_output_field: str | None = None,
    category_collection: str = "categories",
    category_slug_field: str = "slug",
    category_label_field: str = "title",
    category_parent_field: str | None = None,
    category_skip_first: int = 0,
    category_defaults: Mapping[str, Any] | None = None,
    category_depth: int | None = None,
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
            category_field=category_field,
            category_output_field=category_output_field,
            category_collection=category_collection,
            category_slug_field=category_slug_field,
            category_label_field=category_label_field,
            category_parent_field=category_parent_field,
            category_skip_first=category_skip_first,
            category_defaults=category_defaults,
            category_depth=category_depth,
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
