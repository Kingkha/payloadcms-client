from pathlib import Path

from payloadcms_client.articles import ArticlePayloadBuilder
from payloadcms_client.file_parser import parse_article_file


def test_parse_zurich_article(tmp_path: Path) -> None:
    article_text = """---
title: "Zürich Local Culture: Experience Authentic Swiss Life"
date: "2025-08-03"
excerpt: "Discover Zürich local culture, from traditional food and unique customs to vibrant festivals. Plan your authentic Swiss experience in Zürich for 2025!"
featuredImage: "/images/zürich-local-culture.webp"
author: "Editor"
tags:
  - "Travel"
  - "Guide"
  - "Switzerland"
  - "Zürich"
  - "Pillar Content"
  - "Local Experience"
  - "Authentic Travel"
metaDescription: |
  Discover Zürich local culture, from traditional food and unique customs to vibrant festivals. Plan your authentic Swiss experience in Zürich for 2025!
---
<h1>Immerse Yourself in Zürich's Rich Local Culture in 2025</h1>
Zürich, Switzerland's largest city, often surprises visitors with its deep cultural roots despite its modern facade.
"""

    file_path = tmp_path / "zurich.html"
    file_path.write_text(article_text, encoding="utf-8")

    document = parse_article_file(file_path)

    assert document.metadata["title"] == "Zürich Local Culture: Experience Authentic Swiss Life"
    assert document.metadata["tags"] == [
        "Travel",
        "Guide",
        "Switzerland",
        "Zürich",
        "Pillar Content",
        "Local Experience",
        "Authentic Travel",
    ]
    assert document.body.startswith("<h1>Immerse Yourself in Zürich's Rich Local Culture in 2025</h1>")

    builder = ArticlePayloadBuilder()
    slug, payload = builder.build(document)

    assert slug == "zurich-local-culture-experience-authentic-swiss-life"
    assert payload[builder.body_field].startswith(
        "<h1>Immerse Yourself in Zürich's Rich Local Culture in 2025</h1>"
    )
    assert payload[builder.slug_field] == slug
