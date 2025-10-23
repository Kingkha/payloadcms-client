#!/usr/bin/env python
"""Script to clean PayloadCMS by removing all categories, media, and posts."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List

from payloadcms_client import PayloadRESTClient


def delete_all_documents(
    client: PayloadRESTClient,
    collection: str,
    *,
    limit: int = 100,
    verbose: bool = False,
) -> int:
    """Delete all documents from a collection.
    
    Parameters
    ----------
    client:
        Configured PayloadRESTClient instance.
    collection:
        Name of the collection to clean.
    limit:
        Number of documents to fetch per batch. Default: 100.
    verbose:
        If True, print progress messages.
    
    Returns
    -------
    int
        Number of documents deleted.
    """
    total_deleted = 0
    
    while True:
        # Fetch a batch of documents
        try:
            response = client.list_documents(collection, params={"limit": limit})
        except Exception as e:
            print(f"  ✗ Error fetching {collection}: {e}", file=sys.stderr)
            break
        
        docs = response.get("docs", [])
        if not docs:
            break
        
        # Delete each document in the batch
        for doc in docs:
            doc_id = doc.get("id")
            if doc_id is None:
                if verbose:
                    print(f"  ⚠ Skipping document without ID in {collection}")
                continue
            
            try:
                client.delete_document(collection, doc_id)
                total_deleted += 1
                if verbose:
                    doc_title = doc.get("title") or doc.get("name") or doc.get("filename") or doc_id
                    print(f"  ✓ Deleted {collection}/{doc_id}: {doc_title}")
            except Exception as e:
                doc_title = doc.get("title") or doc.get("name") or doc.get("filename") or doc_id
                print(f"  ✗ Error deleting {collection}/{doc_id} ({doc_title}): {e}", file=sys.stderr)
        
        # If we got fewer documents than the limit, we're done
        if len(docs) < limit:
            break
    
    return total_deleted


def clean_payloadcms(
    client: PayloadRESTClient,
    *,
    posts_collection: str = "posts",
    media_collection: str = "media",
    categories_collection: str = "categories",
    clean_posts: bool = True,
    clean_media: bool = True,
    clean_categories: bool = True,
    verbose: bool = False,
) -> Dict[str, int]:
    """Clean PayloadCMS by removing posts, media, and categories.
    
    Parameters
    ----------
    client:
        Configured PayloadRESTClient instance with authentication.
    posts_collection:
        Name of the posts collection. Default: "posts".
    media_collection:
        Name of the media collection. Default: "media".
    categories_collection:
        Name of the categories collection. Default: "categories".
    clean_posts:
        If True, delete all posts. Default: True.
    clean_media:
        If True, delete all media. Default: True.
    clean_categories:
        If True, delete all categories. Default: True.
    verbose:
        If True, print progress messages.
    
    Returns
    -------
    dict
        Dictionary with keys 'posts', 'media', 'categories' and values being
        the number of documents deleted from each collection.
    """
    results: Dict[str, int] = {}
    
    # Delete posts first (they may reference media and categories)
    if clean_posts:
        print(f"\n🗑️  Cleaning {posts_collection}...")
        results["posts"] = delete_all_documents(
            client, posts_collection, verbose=verbose
        )
        print(f"✓ Deleted {results['posts']} posts")
    
    # Delete media
    if clean_media:
        print(f"\n🗑️  Cleaning {media_collection}...")
        results["media"] = delete_all_documents(
            client, media_collection, verbose=verbose
        )
        print(f"✓ Deleted {results['media']} media files")
    
    # Delete categories last
    if clean_categories:
        print(f"\n🗑️  Cleaning {categories_collection}...")
        results["categories"] = delete_all_documents(
            client, categories_collection, verbose=verbose
        )
        print(f"✓ Deleted {results['categories']} categories")
    
    return results


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean PayloadCMS by removing categories, media, and posts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clean everything using credentials from .env file
  python clean_payloadcms.py

  # Clean only posts
  python clean_payloadcms.py --only-posts

  # Clean only media and categories
  python clean_payloadcms.py --skip-posts

  # Clean with verbose output
  python clean_payloadcms.py --verbose

  # Use specific collection names
  python clean_payloadcms.py --posts articles --media files

  # Specify base URL and credentials
  python clean_payloadcms.py --url https://example.com --email user@example.com --password secret
        """,
    )
    
    # Connection options
    parser.add_argument(
        "--url",
        dest="base_url",
        help="PayloadCMS base URL (default: from PAYLOAD_URL env var or http://localhost:3000)",
        default=None,
    )
    parser.add_argument(
        "--email",
        help="Login email (default: from PAYLOAD_EMAIL env var)",
        default=None,
    )
    parser.add_argument(
        "--password",
        help="Login password (default: from PAYLOAD_PASSWORD env var)",
        default=None,
    )
    parser.add_argument(
        "--api-prefix",
        default="api",
        help="API prefix (default: api)",
    )
    
    # Collection names
    parser.add_argument(
        "--posts",
        dest="posts_collection",
        default="posts",
        help="Posts collection name (default: posts)",
    )
    parser.add_argument(
        "--media",
        dest="media_collection",
        default="media",
        help="Media collection name (default: media)",
    )
    parser.add_argument(
        "--categories",
        dest="categories_collection",
        default="categories",
        help="Categories collection name (default: categories)",
    )
    
    # What to clean
    parser.add_argument(
        "--skip-posts",
        action="store_true",
        help="Skip cleaning posts",
    )
    parser.add_argument(
        "--skip-media",
        action="store_true",
        help="Skip cleaning media",
    )
    parser.add_argument(
        "--skip-categories",
        action="store_true",
        help="Skip cleaning categories",
    )
    parser.add_argument(
        "--only-posts",
        action="store_true",
        help="Only clean posts (skip media and categories)",
    )
    parser.add_argument(
        "--only-media",
        action="store_true",
        help="Only clean media (skip posts and categories)",
    )
    parser.add_argument(
        "--only-categories",
        action="store_true",
        help="Only clean categories (skip posts and media)",
    )
    
    # Output options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    
    args = parser.parse_args()
    
    # Determine base URL
    import os
    base_url = args.base_url or os.getenv("PAYLOAD_URL") or "http://localhost:3000"
    
    # Determine what to clean
    clean_posts = not args.skip_posts
    clean_media = not args.skip_media
    clean_categories = not args.skip_categories
    
    if args.only_posts:
        clean_posts = True
        clean_media = False
        clean_categories = False
    elif args.only_media:
        clean_posts = False
        clean_media = True
        clean_categories = False
    elif args.only_categories:
        clean_posts = False
        clean_media = False
        clean_categories = True
    
    # Show what will be cleaned
    print("=" * 60)
    print("PayloadCMS Cleanup Script")
    print("=" * 60)
    print(f"\nBase URL: {base_url}")
    print("\nCollections to clean:")
    if clean_posts:
        print(f"  ✓ Posts: {args.posts_collection}")
    else:
        print(f"  ✗ Posts: skipped")
    if clean_media:
        print(f"  ✓ Media: {args.media_collection}")
    else:
        print(f"  ✗ Media: skipped")
    if clean_categories:
        print(f"  ✓ Categories: {args.categories_collection}")
    else:
        print(f"  ✗ Categories: skipped")
    
    # Confirmation prompt
    if not args.yes:
        print("\n⚠️  WARNING: This will permanently delete all data from the selected collections!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ("yes", "y"):
            print("Cancelled.")
            return 0
    
    # Initialize client and authenticate
    print(f"\n🔐 Authenticating...")
    try:
        client = PayloadRESTClient(
            base_url=base_url,
            api_prefix=args.api_prefix,
        )
        client.login(email=args.email, password=args.password)
        print("✓ Authentication successful")
    except Exception as e:
        print(f"✗ Authentication failed: {e}", file=sys.stderr)
        return 1
    
    # Perform cleanup
    try:
        results = clean_payloadcms(
            client,
            posts_collection=args.posts_collection,
            media_collection=args.media_collection,
            categories_collection=args.categories_collection,
            clean_posts=clean_posts,
            clean_media=clean_media,
            clean_categories=clean_categories,
            verbose=args.verbose,
        )
        
        # Show summary
        print("\n" + "=" * 60)
        print("Cleanup Complete")
        print("=" * 60)
        total = sum(results.values())
        print(f"\nTotal documents deleted: {total}")
        for collection, count in results.items():
            print(f"  {collection}: {count}")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Cleanup failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

