import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from blogboard.config.settings import app_settings


class LocalStorageService:
    """
    Local file system storage - free alternative to Cloudflare R2.
    Stores all blog data in the blogboard/web/blogs/ directory.
    """
    
    def __init__(self):
        """Initialize local storage in the web/blogs directory"""
        self.base_path = Path(__file__).parent.parent / "web" / "blogs"
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_object(self, key: str) -> Optional[str]:
        """
        Read file content from local storage.
        
        Args:
            key: Relative path to the file (e.g., "ml/articles.json")
            
        Returns:
            File content as string, or None if file doesn't exist
        """
        file_path = self.base_path / key
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None
    
    def put_object(self, key: str, data: str, content_type: str = "text/plain") -> bool:
        """
        Write file content to local storage.
        
        Args:
            key: Relative path to the file
            data: Content to write
            content_type: MIME type (ignored for local storage)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self.base_path / key
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(data, encoding="utf-8")
            print(f"  ✅ Saved locally: {file_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save {key}: {e}")
            return False
    
    def get_json(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """
        Read and parse JSON file from local storage.
        
        Args:
            key: Relative path to the JSON file
            
        Returns:
            Parsed JSON data as list, or empty list if file doesn't exist or is invalid
        """
        data = self.get_object(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                print(f"[WARN] Failed to decode JSON from {key}. Starting fresh.")
                return []
        return []
    
    def get_articles_json(self, domain: str) -> List[Dict[str, Any]]:
        """
        Get the articles registry for a specific domain.
        
        Args:
            domain: Domain slug (e.g., "ml", "dl", "nlp")
            
        Returns:
            List of article metadata dictionaries
        """
        return self.get_json(f"{domain}/articles.json") or []
    
    def save_articles_json(self, domain: str, articles: List[Dict[str, Any]]) -> bool:
        """
        Save the articles registry for a specific domain.
        
        Args:
            domain: Domain slug
            articles: List of article metadata dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        json_str = json.dumps(articles, indent=2, ensure_ascii=False)
        return self.put_object(f"{domain}/articles.json", json_str, content_type="application/json")
    
    def get_recent_history(self, domain: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get the N most recent articles for a domain to provide context.
        
        Args:
            domain: Domain slug
            limit: Maximum number of articles to return
            
        Returns:
            List of recent article metadata (pruned to save tokens)
        """
        articles = self.get_articles_json(domain)
        sorted_articles = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)
        recent = sorted_articles[:limit]
        
        # Prune heavy data to save on prompt tokens
        return [{
            "title": a.get("title"),
            "topic": a.get("topic"),
            "subtopics": a.get("subtopics", "")
        } for a in recent]
    
    def get_all_domains_last_updated(self) -> Dict[str, str]:
        """
        Scan all domains and return their latest update dates.

        Returns:
            Dictionary mapping domain slugs to their last update date.
            Domains with no articles get "0000-00-00" so they sort first
            (oldest) and are picked before any domain that already has content.
        """
        latest_dates = {}
        for domain_slug in app_settings.tags.model_dump().keys():
            articles = self.get_articles_json(domain_slug)
            if not articles:
                latest_dates[domain_slug] = "0000-00-00"
            else:
                sorted_articles = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)
                latest_dates[domain_slug] = sorted_articles[0].get("date", "0000-00-00")
        return latest_dates

# Made with Bob
