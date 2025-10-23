#!/usr/bin/env python
"""Example script demonstrating how to clean PayloadCMS programmatically."""

from payloadcms_client import PayloadRESTClient
from clean_payloadcms import clean_payloadcms


def main():
    """Demonstrate cleaning PayloadCMS collections."""
    # Initialize the client
    client = PayloadRESTClient(base_url="https://famoussights-sooty.vercel.app/")
    
    # Authenticate (uses PAYLOAD_EMAIL and PAYLOAD_PASSWORD from .env)
    try:
        print("Authenticating...")
        client.login()
        print("✓ Authentication successful!\n")
        
        # Example 1: Clean everything
        print("Example 1: Clean all collections")
        print("-" * 40)
        results = clean_payloadcms(
            client,
            posts_collection="posts",
            media_collection="media",
            categories_collection="categories",
            clean_posts=True,
            clean_media=True,
            clean_categories=True,
            verbose=True,  # Show detailed progress
        )
        print(f"\nDeleted: {results}")
        
        # Example 2: Clean only posts
        # print("\n\nExample 2: Clean only posts")
        # print("-" * 40)
        # results = clean_payloadcms(
        #     client,
        #     clean_posts=True,
        #     clean_media=False,
        #     clean_categories=False,
        #     verbose=False,
        # )
        # print(f"Deleted {results['posts']} posts")
        
        # Example 3: Clean media and categories but not posts
        # print("\n\nExample 3: Clean media and categories")
        # print("-" * 40)
        # results = clean_payloadcms(
        #     client,
        #     clean_posts=False,
        #     clean_media=True,
        #     clean_categories=True,
        #     verbose=False,
        # )
        # print(f"Deleted {results['media']} media and {results['categories']} categories")
        
    except ValueError as e:
        print(f"✗ Missing credentials: {e}")
        print("\nTo use this example:")
        print("1. Create a .env file with:")
        print("   PAYLOAD_EMAIL=your-email@example.com")
        print("   PAYLOAD_PASSWORD=your-password")
        
    except Exception as e:
        print(f"✗ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

