from __future__ import annotations

from pathlib import Path

import pytest

from payloadcms_client.articles import (
    upload_article_from_file,
    upload_article_with_featured_image,
    upload_articles_from_directory,
)


class RecordingClient:
    def __init__(self, *, existing_media: dict[str, dict] | None = None) -> None:
        self.existing_media = existing_media or {}
        self.media_uploads: list[dict] = []
        self.find_calls: list[dict] = []
        self.article_upserts: list[dict] = []

    def find_first_by_field(
        self,
        collection: str,
        field: str,
        value: str,
        *,
        depth: int | None = None,
    ):
        self.find_calls.append(
            {
                "collection": collection,
                "field": field,
                "value": value,
                "depth": depth,
            }
        )
        if collection == "media":
            return self.existing_media.get(value)
        return None

    def upload_media(
        self,
        collection: str,
        file_path: str | Path,
        *,
        file_field: str = "file",
        data: dict | None = None,
        depth: int | None = None,
    ):
        record = {
            "collection": collection,
            "file_path": Path(file_path),
            "file_field": file_field,
            "data": data or {},
            "depth": depth,
        }
        self.media_uploads.append(record)
        return {
            "id": f"media-{len(self.media_uploads)}",
            "filename": record["file_path"].name,
        }

    def upsert_by_field(
        self,
        *,
        collection: str,
        field: str,
        value: str,
        payload: dict,
        depth: int | None = None,
    ):
        self.article_upserts.append(
            {
                "collection": collection,
                "field": field,
                "value": value,
                "payload": payload,
                "depth": depth,
            }
        )
        return {"id": "article-1", **payload}


@pytest.fixture
def article_file(tmp_path: Path) -> Path:
    article_dir = tmp_path / "posts"
    article_dir.mkdir()
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    image_path = images_dir / "zurich-local-culture.webp"
    image_path.write_bytes(b"fake-image-bytes")

    article = article_dir / "zurich.html"
    article.write_text(
        "---\n"
        "title: Zürich Local Culture\n"
        "featuredImage: \"/images/zurich-local-culture.webp\"\n"
        "---\n"
        "<p>Body</p>\n",
        encoding="utf-8",
    )
    return article


@pytest.fixture
def article_without_featured(tmp_path: Path) -> tuple[Path, Path]:
    article_dir = tmp_path / "posts"
    article_dir.mkdir()
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    image_path = images_dir / "zurich-local-culture.webp"
    image_path.write_bytes(b"fake-image-bytes")

    article = article_dir / "zurich.html"
    article.write_text(
        "---\n"
        "title: Zürich Local Culture\n"
        "---\n"
        "<p>Body</p>\n",
        encoding="utf-8",
    )

    return article, image_path


def test_featured_image_is_uploaded_and_linked(article_file: Path) -> None:
    client = RecordingClient()

    response = upload_article_from_file(
        client=client,
        collection="posts",
        file_path=str(article_file),
        media_root=article_file.parent.parent,
    )

    assert len(client.media_uploads) == 1
    media_call = client.media_uploads[0]
    assert media_call["collection"] == "media"
    assert media_call["file_path"].name == "zurich-local-culture.webp"
    assert media_call["data"] == {}

    assert len(client.article_upserts) == 1
    article_payload = client.article_upserts[0]["payload"]
    assert article_payload["featuredImage"] == "media-1"
    assert response["featuredImage"] == "media-1"


def test_existing_media_is_reused(article_file: Path) -> None:
    client = RecordingClient(
        existing_media={
            "zurich-local-culture.webp": {
                "id": "existing-media",
                "filename": "zurich-local-culture.webp",
            }
        }
    )

    response = upload_article_from_file(
        client=client,
        collection="posts",
        file_path=str(article_file),
        media_root=article_file.parent.parent,
        media_defaults={"alt": "Local culture"},
        media_depth=2,
    )

    assert not client.media_uploads
    assert client.find_calls[0]["depth"] == 2

    article_payload = client.article_upserts[0]["payload"]
    assert article_payload["featuredImage"] == "existing-media"
    assert response["featuredImage"] == "existing-media"


def test_upload_article_with_featured_image_helper_uses_front_matter(article_file: Path) -> None:
    client = RecordingClient()

    response = upload_article_with_featured_image(
        client=client,
        collection="posts",
        file_path=str(article_file),
        media_root=article_file.parent.parent,
    )

    assert len(client.media_uploads) == 1
    uploaded = client.media_uploads[0]
    assert uploaded["file_path"].name == "zurich-local-culture.webp"

    assert len(client.article_upserts) == 1
    payload = client.article_upserts[0]["payload"]
    assert payload["featuredImage"] == "media-1"
    assert response["featuredImage"] == "media-1"


def test_upload_article_with_featured_image_helper_overrides_metadata(
    article_without_featured: tuple[Path, Path]
) -> None:
    article_path, image_path = article_without_featured
    client = RecordingClient()

    response = upload_article_with_featured_image(
        client=client,
        collection="posts",
        file_path=str(article_path),
        featured_image=image_path,
    )

    assert len(client.media_uploads) == 1
    uploaded = client.media_uploads[0]
    assert uploaded["file_path"].resolve() == image_path.resolve()

    assert len(client.article_upserts) == 1
    payload = client.article_upserts[0]["payload"]
    assert payload["featuredImage"] == "media-1"
    assert response["featuredImage"] == "media-1"


def test_upload_articles_from_directory_prefixes_slugs(tmp_path: Path) -> None:
    root = tmp_path / "content"
    root.mkdir()

    (root / "overview.html").write_text(
        "---\n"
        "title: Europe Overview\n"
        "---\n"
        "<p>Root body</p>\n",
        encoding="utf-8",
    )

    italy_dir = root / "Italy"
    italy_dir.mkdir()
    (italy_dir / "rome-activities.html").write_text(
        "---\n"
        "title: Rome Activities\n"
        "---\n"
        "<p>Rome body</p>\n",
        encoding="utf-8",
    )
    (italy_dir / "venice.html").write_text(
        "---\n"
        "slug: italy/venice-guide\n"
        "title: Venice Guide\n"
        "---\n"
        "<p>Venice body</p>\n",
        encoding="utf-8",
    )

    swiss_dir = root / "Switzerland Adventures"
    swiss_dir.mkdir()
    (swiss_dir / "zurich.html").write_text(
        "---\n"
        "title: Zürich Local Culture\n"
        "---\n"
        "<p>Zurich body</p>\n",
        encoding="utf-8",
    )

    client = RecordingClient()

    responses = upload_articles_from_directory(
        client=client,
        collection="posts",
        directory=root,
    )

    assert len(responses) == 4
    assert len(client.article_upserts) == 4

    slugs = {record["value"] for record in client.article_upserts}
    assert slugs == {
        "europe-overview",
        "italy/rome-activities",
        "italy/venice-guide",
        "switzerland-adventures/zurich-local-culture",
    }

    for record in client.article_upserts:
        assert record["value"] == record["payload"]["slug"]
