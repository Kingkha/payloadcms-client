#!/usr/bin/env python
"""Test script to upload a Bologna article to PayloadCMS."""

from pathlib import Path
from payloadcms_client import PayloadRESTClient
from payloadcms_client.articles import (
    upload_article_from_file,
    ArticlePayloadBuilder,
)


def main():
    """Upload Bologna 2-day itinerary article."""
    print("\n" + "=" * 70)
    print("Testing Article Upload: Bologna 2-Day Itinerary")
    print("=" * 70)
    
    # Article and image paths
    article_path = "../scrapbot-article-creator/city_sightseeing_itinerary/italy/bologna/articles/bologna-2-day-itinerary.html"
    # Point media_root to the bologna directory (parent of images)
    # Since the featured image path is "/images/bologna-2-day-itinerary.webp"
    media_root = "../scrapbot-article-creator/city_sightseeing_itinerary/italy/bologna"
    
    # Verify files exist
    if not Path(article_path).exists():
        print(f"✗ Article file not found: {article_path}")
        return
    
    if not Path(media_root).exists():
        print(f"✗ Media root directory not found: {media_root}")
        return
    
    print(f"\n📄 Article: {Path(article_path).name}")
    print(f"📁 Media Root: {media_root}")
    
    # Initialize the PayloadCMS client
    print("\n" + "-" * 70)
    print("Step 1: Initializing PayloadCMS client...")
    print("-" * 70)
    
    client = PayloadRESTClient(base_url="https://famoussights-sooty.vercel.app/")
    
    try:
        # Authenticate
        print("\n🔐 Authenticating...")
        auth_response = client.login()
        print(f"✓ Authenticated as: {auth_response['user']['email']}")
        
        # Create custom builder with default fields
        print("\n" + "-" * 70)
        print("Step 2: Configuring article builder...")
        print("-" * 70)
        
        # Your PayloadCMS collection uses Lexical richText editor
        # So we need to convert HTML to Lexical format
        builder = ArticlePayloadBuilder(
            slug_field="slug",
            body_field="content",
            defaults={
                "status": "draft",  # Start as draft
            },
            convert_to_lexical=True,  # Required for Lexical richText field
        )
        print("✓ Builder configured with 'content' field for body")
        print("  Storage mode: Lexical (converting HTML to Lexical format)")
        print("  Default status: draft")
        
        # Upload the article
        print("\n" + "-" * 70)
        print("Step 3: Uploading article to PayloadCMS...")
        print("-" * 70)
        
        print("\n📤 Processing article...")
        print("  - Parsing YAML front matter")
        print("  - Processing HTML content")
        print("  - Converting HTML to Lexical format")
        print("  - Creating hierarchical categories (Italy → Bologna)")
        print("  - Skipping first 2 tags (Travel, Guide)")
        print("  - Handling featured image")
        print("  - Upserting to CMS...")
        
        response = upload_article_from_file(
            client=client,
            collection="posts",
            file_path=article_path,
            builder=builder,
            depth=1,
            featured_image_field="featuredImage",  # Field name in article YAML
            featured_image_output_field="heroImage",  # Field name in PayloadCMS schema
            media_collection="media",
            media_root=media_root,  # Look for images here
            media_defaults={},  # Empty - will use filename fallback for alt/caption
            media_depth=0,
            slug_prefix="italy/bologna",  # Add location prefix to slug
            category_field="tags",  # Field name in article YAML
            category_output_field="categories",  # Field name in PayloadCMS schema
            category_collection="categories",  # Collection name for categories
            category_slug_field="slug",  # Slug field in categories collection
            category_label_field="title",  # Title field in categories collection
            category_parent_field="parent",  # Parent field for hierarchy
            category_skip_first=2,  # Skip "Travel" and "Guide", then Italy->Bologna
            category_depth=1,  # Populate category details in response
        )
        
        # Display results
        print("\n" + "=" * 70)
        print("✓ UPLOAD SUCCESSFUL!")
        print("=" * 70)
        
        # Handle response structure (may be wrapped in "doc")
        doc = response.get('doc', response)
        
        print(f"\n📊 Article Details:")
        print(f"  ID:            {doc.get('id')}")
        print(f"  Title:         {doc.get('title')}")
        print(f"  Slug:          {doc.get('slug')}")
        print(f"  Status:        {doc.get('_status', doc.get('status'))}")
        print(f"  Author:        {doc.get('author')}")
        
        # Show excerpt/description if available
        excerpt = doc.get('excerpt') or doc.get('metaDescription')
        if excerpt:
            print(f"  Excerpt:       {str(excerpt)[:80]}...")
        
        # Featured image info
        featured_image = doc.get('featuredImage') or doc.get('heroImage')
        if featured_image:
            if isinstance(featured_image, dict):
                print(f"\n🖼️  Featured Image:")
                print(f"  ID:            {featured_image.get('id')}")
                print(f"  Filename:      {featured_image.get('filename')}")
                print(f"  Alt:           {featured_image.get('alt')}")
            else:
                print(f"\n🖼️  Featured Image ID: {featured_image}")
        
        # Tags/Categories
        tags = doc.get('tags', []) or doc.get('categories', [])
        if tags:
            # Tags could be IDs (strings) or full objects with title/name
            tag_list = []
            for t in tags:
                if isinstance(t, dict):
                    # It's a populated object
                    tag_list.append(t.get('name', t.get('title', str(t))))
                elif isinstance(t, (str, int)):
                    # It's just an ID
                    tag_list.append(f"ID:{t}")
                else:
                    tag_list.append(str(t))
            print(f"\n🏷️  Categories/Tags ({len(tag_list)}):")
            for i, t in enumerate(tags, 1):
                if isinstance(t, dict):
                    title = t.get('title', t.get('name', 'N/A'))
                    parent = t.get('parent')
                    parent_info = ""
                    if parent:
                        if isinstance(parent, dict):
                            parent_info = f" (child of: {parent.get('title', parent.get('id'))})"
                        else:
                            parent_info = f" (parent ID: {parent})"
                    print(f"  {i}. {title}{parent_info}")
                    print(f"     ID: {t.get('id')}, Slug: {t.get('slug')}")
                elif isinstance(t, (str, int)):
                    print(f"  {i}. ID: {t}")
                else:
                    print(f"  {i}. {t}")
        
        print(f"\n🔗 View in CMS: https://famoussights-sooty.vercel.app/admin/collections/posts/{doc.get('id')}")
        
        print("\n" + "=" * 70)
        print("Test completed successfully!")
        print("=" * 70)
        
    except ValueError as e:
        print(f"\n✗ Configuration Error: {e}")
        print("\nMake sure you have a .env file with:")
        print("  PAYLOAD_EMAIL=your-email@example.com")
        print("  PAYLOAD_PASSWORD=your-password")
        return 1
        
    except FileNotFoundError as e:
        print(f"\n✗ File Error: {e}")
        return 1
        
    except Exception as e:
        print(f"\n✗ Upload Failed: {e}")
        
        # Try to get more details from the response
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print("\n📋 PayloadCMS Error Response:")
                import json
                print(json.dumps(error_data, indent=2))
            except:
                print(f"\nResponse text: {e.response.text}")
        
        import traceback
        print("\nFull error details:")
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

