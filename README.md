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

### Cleaning PayloadCMS collections

The package includes utilities to delete all documents from specified collections.
This is useful for testing, resetting your development environment, or cleaning
up before a fresh data import.

#### Using the command-line script

The `clean_payloadcms.py` script provides a convenient way to clean collections:

```bash
# Clean everything (posts, media, and categories)
python clean_payloadcms.py

# Clean only posts
python clean_payloadcms.py --only-posts

# Clean only media and categories (skip posts)
python clean_payloadcms.py --skip-posts

# Show detailed progress
python clean_payloadcms.py --verbose

# Use custom collection names
python clean_payloadcms.py --posts articles --media files

# Skip confirmation prompt
python clean_payloadcms.py --yes

# Specify credentials directly
python clean_payloadcms.py --url https://example.com --email user@example.com --password secret
```

The script requires authentication and will use `PAYLOAD_EMAIL` and `PAYLOAD_PASSWORD`
from your `.env` file by default.

**⚠️ Warning:** This operation permanently deletes data and cannot be undone. The
script will prompt for confirmation unless you pass the `--yes` flag.

#### Using the cleanup function programmatically

You can also use the cleanup functionality in your Python code:

```python
from payloadcms_client import PayloadRESTClient
from clean_payloadcms import clean_payloadcms

# Authenticate
client = PayloadRESTClient(base_url="http://localhost:3000")
client.login()

# Clean everything
results = clean_payloadcms(
    client,
    posts_collection="posts",
    media_collection="media",
    categories_collection="categories",
    clean_posts=True,
    clean_media=True,
    clean_categories=True,
    verbose=True,
)

print(f"Deleted {results['posts']} posts")
print(f"Deleted {results['media']} media files")
print(f"Deleted {results['categories']} categories")

# Clean only specific collections
results = clean_payloadcms(
    client,
    clean_posts=True,
    clean_media=False,
    clean_categories=False,
)
```

The cleanup function processes collections in a safe order:
1. **Posts first** – removed before media/categories to avoid orphaned references
2. **Media** – removed after posts that might reference them
3. **Categories** – removed last since they're often referenced by other collections

## Performance

The library is optimized for bulk article uploads with minimal API calls:

- **Batch category lookups** – Instead of checking each category individually (2 API calls per category), all categories are looked up in a single API call, reducing overhead by 25-45% depending on the number of categories.
- **Smart media reuse** – Featured images are automatically reused if they already exist in the media collection, avoiding duplicate uploads.
- **Efficient upserts** – Articles are updated in-place if they already exist (matched by slug), preserving IDs and relationships.

For a typical article with 2 categories and a new featured image:
- **Initial upload**: ~8 API calls (1 batch category lookup + 2 category creates + 1 image check + 1 image upload + 1 image update + 1 article check + 1 article create)
- **Subsequent updates**: ~6 API calls when categories and images already exist (33% faster)

See [PERFORMANCE.md](PERFORMANCE.md) for detailed benchmarks and optimization details.

## Development

```bash
pip install -e .[dev]
```

Environment variables can be loaded using `python-dotenv` if desired. Tests are
not included in this initial version; integrate your preferred test framework as
needed.
