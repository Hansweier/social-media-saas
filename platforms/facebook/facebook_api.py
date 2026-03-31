import requests
import logging

log = logging.getLogger(__name__)


def _safe_json(response, default=None):
    """Gibt response.json() zurück oder default bei Parse-Fehler."""
    try:
        return response.json()
    except Exception:
        log.error(f"Facebook API: ungültige JSON-Antwort (HTTP {response.status_code}): {response.text[:200]}")
        return default if default is not None else {}


class FacebookAPI:
    def __init__(self, access_token, page_id):
        self.token = access_token
        self.page_id = page_id
        self.base_url = "https://graph.facebook.com/v18.0"

    def post_text(self, message):
        """Text-Post auf Facebook Seite veröffentlichen"""
        url = f"{self.base_url}/{self.page_id}/feed"
        data = {
            "message": message,
            "access_token": self.token
        }
        response = requests.post(url, data=data)
        return _safe_json(response)

    def post_with_image(self, message, image_url):
        """Post mit Bild veröffentlichen"""
        url = f"{self.base_url}/{self.page_id}/photos"
        data = {
            "message": message,
            "url": image_url,
            "access_token": self.token
        }
        response = requests.post(url, data=data)
        return _safe_json(response)

    def get_posts(self, limit=10):
        """Letzte Posts abrufen"""
        url = f"{self.base_url}/{self.page_id}/posts"
        params = {
            "fields": "id,message,created_time,likes.summary(true),comments.summary(true)",
            "limit": limit,
            "access_token": self.token
        }
        response = requests.get(url, params=params)
        return _safe_json(response, {}).get("data", [])

    def get_comments(self, post_id):
        """Kommentare eines Posts abrufen"""
        url = f"{self.base_url}/{post_id}/comments"
        params = {
            "fields": "id,message,from,created_time",
            "access_token": self.token
        }
        response = requests.get(url, params=params)
        return _safe_json(response, {}).get("data", [])

    def reply_to_comment(self, comment_id, message):
        """Auf Kommentar antworten"""
        url = f"{self.base_url}/{comment_id}/comments"
        data = {
            "message": message,
            "access_token": self.token
        }
        response = requests.post(url, data=data)
        return _safe_json(response)

    def get_messages(self):
        """Facebook Messenger Nachrichten abrufen"""
        url = f"{self.base_url}/me/conversations"
        params = {
            "fields": "messages{message,from,created_time}",
            "access_token": self.token
        }
        response = requests.get(url, params=params)
        return _safe_json(response, {}).get("data", [])

    def send_message(self, recipient_id, message):
        """Facebook Messenger Nachricht senden"""
        url = f"{self.base_url}/me/messages"
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message},
            "access_token": self.token
        }
        response = requests.post(url, json=data)
        return _safe_json(response)

    def get_page_insights(self):
        """Seitenstatistiken abrufen"""
        url = f"{self.base_url}/{self.page_id}/insights"
        params = {
            "metric": "page_fans,page_views_total,page_post_engagements",
            "period": "week",
            "access_token": self.token
        }
        response = requests.get(url, params=params)
        return _safe_json(response, {}).get("data", [])
