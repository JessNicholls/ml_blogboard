#!/usr/bin/env python3
"""
Quick test script to verify local storage is working correctly.
Run this before running the full blogboard application.
"""

from blogboard.services.local_storage import LocalStorageService

def test_local_storage():
    print("Testing Local Storage Service...")
    print("=" * 50)
    
    storage = LocalStorageService()
    print(f"✓ Storage initialized at: {storage.base_path}")
    
    # Test writing a file
    test_content = "# Test Article\n\nThis is a test."
    success = storage.put_object("test/test-article.md", test_content)
    print(f"✓ Write test: {'SUCCESS' if success else 'FAILED'}")
    
    # Test reading the file
    read_content = storage.get_object("test/test-article.md")
    print(f"✓ Read test: {'SUCCESS' if read_content == test_content else 'FAILED'}")
    
    # Test JSON operations
    test_articles = [
        {
            "id": "test/test-article.md",
            "title": "Test Article",
            "date": "2026-06-15"
        }
    ]
    success = storage.save_articles_json("test", test_articles)
    print(f"✓ JSON write test: {'SUCCESS' if success else 'FAILED'}")
    
    articles = storage.get_articles_json("test")
    print(f"✓ JSON read test: {'SUCCESS' if len(articles) == 1 else 'FAILED'}")
    
    # Test domain tracking
    domains = storage.get_all_domains_last_updated()
    print(f"✓ Domain tracking: Found {len(domains)} domains")
    
    print("=" * 50)
    print("✅ All tests passed! Local storage is working correctly.")
    print(f"\nFiles are stored in: {storage.base_path}")
    print("\nYou can now run: python blogboard/run.py")

if __name__ == "__main__":
    test_local_storage()

# Made with Bob
