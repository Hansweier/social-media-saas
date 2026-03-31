import requests
import logging

log = logging.getLogger(__name__)


def _safe_json(response, default=None):
    """Gibt response.json() zurück oder default bei Parse-Fehler."""
    if default is None:
        default = {}
    try:
        return response.json()
    except Exception:
        log.error(f"Instagram API: ungültige JSON-Antwort (HTTP {response.status_code}): {response.text[:200]}")
        return default


class InstagramAPI:
    def __init__(self, access_token, account_id):
        self.token = access_token
        self.account_id = account_id
        self.base_url = "https://graph.instagram.com/v18.0"

    def post_image(self, image_url, caption):
        """Bild auf Instagram posten"""
        container_url = f"{self.base_url}/{self.account_id}/media"
        container_data = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.token
        }
        response = requests.post(container_url, data=container_data)
        data = _safe_json(response)
        container_id = data.get("id")

        if not container_id:
            log.error(f"Instagram container fehlgeschlagen: {data}")
            return data or {"error": f"HTTP {response.status_code}"}

        publish_url = f"{self.base_url}/{self.account_id}/media_publish"
        publish_data = {
            "creation_id": container_id,
            "access_token": self.token
        }
        r2 = requests.post(publish_url, data=publish_data)
        return _safe_json(r2)

    def post_reel(self, video_url, caption):
        """Reel auf Instagram posten"""
        container_url = f"{self.base_url}/{self.account_id}/media"
        container_data = {
            "video_url": video_url,
            "caption": caption,
            "media_type": "REELS",
            "access_token": self.token
        }
        response = requests.post(container_url, data=container_data)
        data = _safe_json(response)
        container_id = data.get("id")

        if not container_id:
            return data or {"error": f"HTTP {response.status_code}"}

        publish_url = f"{self.base_url}/{self.account_id}/media_publish"
        publish_data = {
            "creation_id": container_id,
            "access_token": self.token
        }
        r2 = requests.post(publish_url, data=publish_data)
        return _safe_json(r2)

    def get_comments(self, post_id):
        """Kommentare abrufen"""
        url = f"{self.base_url}/{post_id}/comments"
        params = {
            "fields": "id,text,username,timestamp",
            "access_token": self.token
        }
        return _safe_json(requests.get(url, params=params), {}).get("data", [])

    def reply_to_comment(self, post_id, message):
        """Auf Kommentar antworten"""
        url = f"{self.base_url}/{post_id}/replies"
        data = {"message": message, "access_token": self.token}
        return _safe_json(requests.post(url, data=data))

    def get_mentions(self):
        """Mentions abrufen"""
        url = f"{self.base_url}/{self.account_id}/tags"
        params = {
            "fields": "id,caption,media_type,timestamp",
            "access_token": self.token
        }
        return _safe_json(requests.get(url, params=params), {}).get("data", [])

    def send_dm(self, recipient_id, message):
        """DM senden"""
        url = "https://graph.facebook.com/v18.0/me/messages"
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message},
            "access_token": self.token
        }
        return _safe_json(requests.post(url, json=data))

    def get_insights(self, post_id):
        """Post-Statistiken abrufen"""
        url = f"{self.base_url}/{post_id}/insights"
        params = {
            "metric": "impressions,reach,likes,comments,shares,saved",
            "access_token": self.token
        }
        return _safe_json(requests.get(url, params=params), {}).get("data", [])
