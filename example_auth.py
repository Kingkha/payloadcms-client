#!/usr/bin/env python
"""Example script demonstrating PayloadCMS authentication."""

from payloadcms_client import PayloadRESTClient


def main():
    """Demonstrate authentication with PayloadCMS."""
    # Initialize the client
    client = PayloadRESTClient(base_url="https://famoussights-sooty.vercel.app/")
    
    # Option 1: Login using environment variables from .env file
    # Make sure you have PAYLOAD_EMAIL and PAYLOAD_PASSWORD in your .env
    try:
        print("Attempting to login...")
        response = client.login()
        
        print(f"✓ Authentication successful!")
        print(f"  User: {response['user']['email']}")
        print(f"  User ID: {response['user']['id']}")
        print(f"  Token expires at: {response['exp']}")
        
        # The token is now stored in client.token
        # All subsequent requests will include the Authorization header
        
        # Example: List documents from a collection
        print("\nFetching posts...")
        posts = client.list_documents("posts")
        print(f"  Found {len(posts.get('docs', []))} posts")
        
    except ValueError as e:
        print(f"✗ Missing credentials: {e}")
        print("\nTo use this example:")
        print("1. Create a .env file with:")
        print("   PAYLOAD_EMAIL=your-email@example.com")
        print("   PAYLOAD_PASSWORD=your-password")
        print("2. Or pass credentials directly to login():")
        print("   client.login(email='...', password='...')")
        
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        print("\nMake sure:")
        print("1. Your PayloadCMS instance is running")
        print("2. The credentials are correct")
        print("3. The base_url is correct")


if __name__ == "__main__":
    main()

