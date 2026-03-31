"""
Poster — kümmert sich ums tatsächliche Veröffentlichen auf jeder Plattform.
Wird vom Scheduler aufgerufen.
"""
import os
import sys
import logging
sys.stdout.reconfigure(encoding='utf-8')

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

log = logging.getLogger(__name__)

from platforms.instagram.instagram_api import InstagramAPI
from platforms.instagram.instagram_content import InstagramContent
from platforms.linkedin.linkedin_api import LinkedInAPI
from platforms.linkedin.linkedin_content import LinkedInContent
from platforms.facebook.facebook_api import FacebookAPI
from platforms.facebook.facebook_content import FacebookContent
from platforms.tiktok.tiktok_content import TikTokContent
from platforms.twitter.twitter_api import TwitterAPI
from platforms.twitter.twitter_content import TwitterContent


class Poster:
    def __init__(self, config: dict):
        self.config = config
        self.api_key = config["claude"]["api_key"]
        self._apis = {}
        self._generators = {}

    def _get_instagram(self):
        if "instagram" not in self._apis:
            token = self.config["instagram"]["access_token"]
            acc_id = self.config["instagram"]["account_id"]
            if not token or "dein_token" in token:
                return None, None
            self._apis["instagram"] = InstagramAPI(token, acc_id)
            self._generators["instagram"] = InstagramContent(self.api_key)
        return self._apis["instagram"], self._generators["instagram"]

    def _get_linkedin(self):
        if "linkedin" not in self._apis:
            token = self.config["linkedin"]["access_token"]
            person_id = self.config["linkedin"]["person_id"]
            if not token or "dein_token" in token:
                return None, None
            self._apis["linkedin"] = LinkedInAPI(token)
            self._generators["linkedin"] = LinkedInContent(self.api_key)
        return self._apis["linkedin"], self._generators["linkedin"]

    def _get_facebook(self):
        if "facebook" not in self._apis:
            token = self.config["facebook"]["access_token"]
            page_id = self.config["facebook"]["page_id"]
            if not token or "dein_token" in token:
                return None, None
            self._apis["facebook"] = FacebookAPI(token, page_id)
            self._generators["facebook"] = FacebookContent(self.api_key)
        return self._apis["facebook"], self._generators["facebook"]

    def _get_twitter(self):
        if "twitter" not in self._apis:
            cfg = self.config["twitter"]
            if not cfg["api_key"] or "dein" in cfg["api_key"]:
                return None, None
            self._apis["twitter"] = TwitterAPI(
                cfg["api_key"], cfg["api_secret"],
                cfg["access_token"], cfg["access_token_secret"],
                cfg["bearer_token"]
            )
            self._generators["twitter"] = TwitterContent(self.api_key)
        return self._apis["twitter"], self._generators["twitter"]

    def generate_content(self, platform: str, topic: str) -> str:
        """Generiert Content für eine Plattform und ein Thema."""
        gen_map = {
            "instagram": lambda g, t: g.generate_caption(t),
            "linkedin":  lambda g, t: g.generate_post(t),
            "facebook":  lambda g, t: g.generate_post(t),
            "tiktok":    lambda g, t: g.generate_caption(t),
            "twitter":   lambda g, t: g.generate_tweet(t),
        }
        if platform not in gen_map:
            raise ValueError(f"Unbekannte Plattform: {platform}")

        # Generator laden
        if platform == "instagram":
            gen = InstagramContent(self.api_key)
        elif platform == "linkedin":
            gen = LinkedInContent(self.api_key)
        elif platform == "facebook":
            gen = FacebookContent(self.api_key)
        elif platform == "tiktok":
            gen = TikTokContent(self.api_key)
        elif platform == "twitter":
            gen = TwitterContent(self.api_key)

        return gen_map[platform](gen, topic)

    def post(self, platform: str, content: str, topic: str, image_url: str = None) -> dict:
        """
        Veröffentlicht einen Post auf der angegebenen Plattform.
        Gibt zurück: {"success": bool, "post_id": str, "error": str}
        Automatischer Retry mit Exponential Backoff (bis zu 4 Versuche).
        """
        @retry(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=2, min=5, max=120),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        def _attempt():
            if platform == "instagram":
                return self._post_instagram(content, image_url)
            elif platform == "linkedin":
                return self._post_linkedin(content)
            elif platform == "facebook":
                return self._post_facebook(content, image_url)
            elif platform == "tiktok":
                return self._post_tiktok(content)
            elif platform == "twitter":
                return self._post_twitter(content)
            else:
                return {"success": False, "error": f"Plattform {platform} unbekannt"}

        try:
            return _attempt()
        except Exception as e:
            log.error(f"[{platform}] Posting nach 4 Versuchen fehlgeschlagen: {e}")
            return {"success": False, "error": str(e)}

    def _post_instagram(self, caption: str, image_url: str = None) -> dict:
        api, _ = self._get_instagram()
        if not api:
            return {"success": False, "error": "Instagram API nicht konfiguriert"}

        if not image_url:
            # Fallback: Placeholder-Bild (in Produktion durch echtes Bild ersetzen)
            image_url = "https://via.placeholder.com/1080x1080.png?text=Foerderkraft"

        result = api.post_image(image_url, caption)
        if result and "id" in result:
            return {"success": True, "post_id": result["id"]}
        return {"success": False, "error": str(result)}

    def _post_linkedin(self, text: str) -> dict:
        api, _ = self._get_linkedin()
        if not api:
            return {"success": False, "error": "LinkedIn API nicht konfiguriert"}

        person_id = self.config["linkedin"]["person_id"]
        result = api.post_text(text, person_id)
        if result and "id" in result:
            return {"success": True, "post_id": result["id"]}
        return {"success": False, "error": str(result)}

    def _post_facebook(self, message: str, image_url: str = None) -> dict:
        api, _ = self._get_facebook()
        if not api:
            return {"success": False, "error": "Facebook API nicht konfiguriert"}

        if image_url:
            result = api.post_with_image(message, image_url)
        else:
            result = api.post_text(message)

        if result and "id" in result:
            return {"success": True, "post_id": result["id"]}
        return {"success": False, "error": str(result)}

    def _post_tiktok(self, caption: str) -> dict:
        # TikTok erfordert Video-Upload — hier wird Inhalt nur geloggt
        # bis Video-Upload implementiert ist
        return {
            "success": False,
            "error": "TikTok Video-Upload noch nicht implementiert — Caption gespeichert"
        }

    def _post_twitter(self, text: str) -> dict:
        api, _ = self._get_twitter()
        if not api:
            return {"success": False, "error": "Twitter API nicht konfiguriert"}

        result = api.post_tweet(text)
        if result and "data" in result:
            return {"success": True, "post_id": result["data"]["id"]}
        return {"success": False, "error": str(result)}
