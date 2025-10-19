"""Public package exports for Payload CMS REST helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .articles import (
        ArticlePayloadBuilder,
        ensure_categories,
        upload_article_from_file,
        upload_article_with_featured_image,
        upload_articles_from_directory,
    )
    from .file_parser import ArticleDocument, parse_article_file
    from .payload_client import PayloadRESTClient

__all__ = [
    "ArticleDocument",
    "ArticlePayloadBuilder",
    "ensure_categories",
    "PayloadRESTClient",
    "parse_article_file",
    "upload_article_from_file",
    "upload_article_with_featured_image",
    "upload_articles_from_directory",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - thin import wrapper
    if name == "ArticleDocument" or name == "parse_article_file":
        from .file_parser import ArticleDocument, parse_article_file

        return ArticleDocument if name == "ArticleDocument" else parse_article_file

    if name in {
        "ArticlePayloadBuilder",
        "upload_article_from_file",
        "upload_article_with_featured_image",
        "upload_articles_from_directory",
        "ensure_categories",
    }:
        from .articles import (
            ArticlePayloadBuilder,
            ensure_categories,
            upload_article_from_file,
            upload_article_with_featured_image,
            upload_articles_from_directory,
        )

        if name == "ArticlePayloadBuilder":
            return ArticlePayloadBuilder
        if name == "upload_article_from_file":
            return upload_article_from_file
        if name == "upload_article_with_featured_image":
            return upload_article_with_featured_image
        if name == "upload_articles_from_directory":
            return upload_articles_from_directory
        return ensure_categories

    if name == "PayloadRESTClient":
        from .payload_client import PayloadRESTClient

        return PayloadRESTClient

    raise AttributeError(name)


def __dir__() -> list[str]:  # pragma: no cover - module metadata
    return sorted(__all__ + ["articles", "file_parser", "payload_client"])
