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
    upload_articles_from_directory,
)

client = PayloadRESTClient(
    base_url="https://your-payload-instance.com",
    token="<your-api-token>",  # optional, if your API is public
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
need to be resolved relative to a specific directory.

Companion fields such as ``featuredImageAlt`` and ``featuredImageCaption`` are
automatically extracted from the article's front matter and transferred to the
media document as ``alt`` and ``caption`` fields. These companion fields are
then removed from the article payload to avoid duplication. For example:

```yaml
---
title: Beautiful Lake Como
featuredImage: /images/lake-como.jpg
featuredImageAlt: Aerial view of Lake Como at sunset
featuredImageCaption: Lake Como, Northern Italy
author: Travel Editor
---
```

If ``featuredImageAlt`` or ``featuredImageCaption`` are not provided, the system
automatically uses the image filename (cleaned and formatted) as a fallback for
both fields. For instance, ``lake-como-sunset.jpg`` becomes ``"Lake Como Sunset"``.

The media document will be created/updated with ``alt`` and ``caption`` fields,
while the article will only reference the media ID through ``featuredImage``.

**⚠️ Important:** Your Payload CMS media collection schema must include ``alt``
and ``caption`` fields for them to be saved. The ``caption`` field is automatically
converted to Lexical richText format if your schema uses it. See
``PAYLOAD_CMS_MEDIA_SCHEMA.md`` for schema setup instructions.

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

#### Using the login method

The client now supports authentication via the Payload CMS login API. You can authenticate in two ways:

**1. Using environment variables (recommended):**

Create a `.env` file in your project root:

```env
PAYLOAD_EMAIL=dev@payloadcms.com
PAYLOAD_PASSWORD=your_password
PAYLOAD_URL=http://localhost:3000
```

Then use the `login()` method:

```python
from payloadcms_client import PayloadRESTClient

client = PayloadRESTClient(base_url="http://localhost:3000")
response = client.login()  # Automatically loads credentials from .env

print(f"Authenticated as: {response['user']['email']}")
print(f"Token expires: {response['exp']}")
# Token is now stored in client.token and will be used for all subsequent requests
```

**2. Passing credentials directly:**

```python
client = PayloadRESTClient(base_url="http://localhost:3000")
response = client.login(
    email="dev@payloadcms.com",
    password="your_password",
    user_collection="users"  # default is "users"
)
```

The `login()` method:
- Makes a POST request to `/api/{user-collection}/login`
- Stores the returned token in `client.token` for subsequent requests
- Returns the full response including user info, token, and expiration time

#### Using a pre-existing token

Alternatively, provide a `token` when instantiating `PayloadRESTClient` to include an
`Authorization` header with every request. The default token type is `Bearer`,
which suits standard REST API keys. If your Payload project expects JWT-based
headers (`JWT <token>`), pass `token_type="JWT"` to the client.

```python
client = PayloadRESTClient(
    base_url="https://your-payload-instance.com",
    token="<your-api-token>",
)
```

### Error handling

Any non-2xx response from Payload CMS raises a `requests.HTTPError`. Wrap calls
in your own error handling if you need custom retry or logging behaviour.

## Development

```bash
pip install -e .[dev]
```

Environment variables can be loaded using `python-dotenv` if desired. Tests are
not included in this initial version; integrate your preferred test framework as
needed.
