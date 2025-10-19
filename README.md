# Payload CMS REST Utilities (Python)

Utilities for parsing HTML article files that include YAML front matter and
syncing them to [Payload CMS](https://payloadcms.com/) collections using the
[REST API](https://payloadcms.com/docs/rest-api/overview).

## Installation

```bash
pip install git+https://example.com/your/payloadcms-client.git
```

Or clone the repository and install in editable mode:

```bash
git clone https://example.com/your/payloadcms-client.git
cd payloadcms-client
pip install -e .
```

The package depends on `requests` for HTTP calls and `PyYAML` for parsing the
front matter metadata.

## Usage

```python
from payloadcms_client import (
    ArticlePayloadBuilder,
    PayloadRESTClient,
    ensure_categories,
    upload_article_from_file,
    upload_article_with_featured_image,
    upload_articles_from_directory,
)

client = PayloadRESTClient(
    base_url="https://your-payload-instance.com",
    token="<your-api-token>",  # optional, if your API is public
)

# Or authenticate with a user collection to fetch a short-lived token
client.login(
    "users",  # replace with your auth-enabled collection
    email="dev@payloadcms.com",
    password="password",
)

response = upload_article_from_file(
    client=client,
    collection="posts",
    file_path="./articles/bellagio-2025.html",
    builder=ArticlePayloadBuilder(
        defaults={
            "status": "published",
            "author": "Editor",
        },
        body_field="content",
    ),
    media_root="./public",  # resolve `/images/...` paths relative to this directory
    media_defaults={"alt": "Bellagio festival fireworks"},
)

print(response)

# Process a single article; featured image paths in front matter are resolved automatically
upload_article_with_featured_image(
    client=client,
    collection="posts",
    file_path="./articles/zurich.html",
    media_root="./public",
)

# Or override the featured image path at call time (handy for tests/fixtures)
upload_article_with_featured_image(
    client=client,
    collection="posts",
    file_path="./articles/zurich.html",
    featured_image="./tests/fixtures/zurich-cover.webp",
)

# Upload every article inside `./content`, prefixing slugs by folder names
bulk_responses = upload_articles_from_directory(
    client=client,
    collection="posts",
    directory="./content",
    media_root="./public",
)

print(len(bulk_responses))

# Ensure related categories exist and capture their IDs
categories = ensure_categories(
    client,
    ["Travel", "Italy"],
    collection="categories",
    defaults={"status": "published"},
)
category_ids = [category["id"] for category in categories]
```

### What the helper does

1. **Parse the HTML file** – The file must start with a YAML front matter block
   delimited by `---` lines. The metadata must contain at least a `title` or a
   `slug` value.
2. **Build a payload** – The metadata is merged with any defaults and the HTML
   body is injected into the configured `body_field` (defaults to `content`). If
   no slug is present, it is automatically derived from the title.
3. **Upsert via REST** – The helper searches the given collection for an
   existing document where the slug field matches. If found, it updates the
   document; otherwise, it creates a new one.

Use `ensure_categories` to guarantee that taxonomy documents exist before
linking them to articles. Provide an iterable of category names and the helper
will slugify, upsert, and return the resulting documents so you can extract IDs
for relationship fields.

When the article metadata contains a ``featuredImage`` string path, the helper
attempts to reuse an existing media document whose filename matches the local
file. If none exists, the file is uploaded to the ``media`` collection (or your
custom collection) and the article payload is updated to reference the media
document ID automatically. Configure ``media_root`` when featured image paths
need to be resolved relative to a specific directory, or pass
``featured_image=...`` to ``upload_article_with_featured_image`` to override the
path for ad-hoc uploads and tests.

Use ``upload_articles_from_directory`` to scan a directory tree for HTML files
with front matter. Each article is uploaded using ``upload_article_from_file``
and its slug is automatically prefixed by the relative folder structure (e.g.
``italy/rome-activities.html`` becomes ``italy/rome-activities``). Pass custom
``pattern`` or ``recursive`` values to control which files are processed.

### Customising the payload

You can subclass `ArticlePayloadBuilder` or provide an alternate builder that
implements a `build(document: ArticleDocument) -> tuple[str, dict]` method if
you need to transform metadata before uploading. The returned payload is sent to
Payload CMS without modification, so you can include relationship IDs, uploads,
or any other supported fields.

### Handling authentication

Provide a `token` when instantiating `PayloadRESTClient` to include an
`Authorization` header with every request. The default token type is `Bearer`,
which suits standard REST API keys. If your Payload project expects JWT-based
headers (`JWT <token>`), pass `token_type="JWT"` to the client. To log in and
retrieve a session token dynamically, call `client.login("users", env_path=".env")`
(replace `"users"` with your auth-enabled collection). The helper reads
`PAYLOADCMS_EMAIL` and `PAYLOADCMS_PASSWORD` from the specified `.env` file (or
from `.env` in the current working directory) and stores the returned token for
subsequent requests automatically. You can override the variable names via the
`email_var` and `password_var` parameters or continue passing explicit `email`
and `password` values when preferred.

### Error handling

Any non-2xx response from Payload CMS raises a `requests.HTTPError`. Wrap calls
in your own error handling if you need custom retry or logging behaviour.

## Development

```bash
pip install -e .[dev]
```

Install the optional `dev` extras to run the test suite locally with `pytest`.
