import requests
from requests_oauthlib import OAuth1

class TwitterAPI:
    def __init__(self, api_key, api_secret, access_token, access_token_secret, bearer_token):
        self.bearer_token = bearer_token
        self.auth = OAuth1(api_key, api_secret, access_token, access_token_secret)
        self.base_url = "https://api.twitter.com/2"
        self.headers = {"Authorization": f"Bearer {self.bearer_token}"}
        self._user_id = None  # lazy-fetched on first use

    def _get_user_id(self) -> str:
        """Eigene User-ID per /2/me abrufen (wird gecacht)."""
        if not self._user_id:
            try:
                r = requests.get(f"{self.base_url}/users/me", auth=self.auth)
                self._user_id = r.json().get("data", {}).get("id", "")
            except Exception:
                self._user_id = ""
        return self._user_id

    def post_tweet(self, text):
        """Tweet veröffentlichen"""
        url = f"{self.base_url}/tweets"
        data = {"text": text}
        response = requests.post(url, auth=self.auth, json=data)
        return response.json()

    def reply_to_tweet(self, tweet_id, text):
        """Auf Tweet antworten"""
        url = f"{self.base_url}/tweets"
        data = {
            "text": text,
            "reply": {"in_reply_to_tweet_id": tweet_id}
        }
        response = requests.post(url, auth=self.auth, json=data)
        return response.json()

    def get_mentions(self, user_id=None):
        """Mentions abrufen. user_id wird automatisch ermittelt wenn nicht angegeben."""
        uid = user_id or self._get_user_id()
        if not uid:
            return []
        url = f"{self.base_url}/users/{uid}/mentions"
        params = {
            "tweet.fields": "created_at,author_id,text",
            "max_results": 20
        }
        response = requests.get(url, headers=self.headers, params=params)
        return response.json().get("data", [])

    def get_dm_conversations(self, dm_event_types="MessageCreate"):
        """Neueste DM-Events des eigenen Accounts abrufen."""
        uid = self._get_user_id()
        if not uid:
            return []
        url = f"{self.base_url}/users/{uid}/dm_events"
        params = {"event_types": dm_event_types, "max_results": 20}
        response = requests.get(url, auth=self.auth, params=params)
        return response.json().get("data", [])

    def send_dm(self, participant_id, text):
        """DM senden"""
        url = f"{self.base_url}/dm_conversations/with/{participant_id}/messages"
        data = {"text": text}
        response = requests.post(url, auth=self.auth, json=data)
        return response.json()

    def like_tweet(self, user_id, tweet_id):
        """Tweet liken"""
        url = f"{self.base_url}/users/{user_id}/likes"
        data = {"tweet_id": tweet_id}
        response = requests.post(url, auth=self.auth, json=data)
        return response.json()

    def retweet(self, user_id, tweet_id):
        """Tweet retweeten"""
        url = f"{self.base_url}/users/{user_id}/retweets"
        data = {"tweet_id": tweet_id}
        response = requests.post(url, auth=self.auth, json=data)
        return response.json()

    def search_tweets(self, query, max_results=10):
        """Tweets suchen (z.B. nach Branche oder Konkurrenz)"""
        url = f"{self.base_url}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,author_id,text,public_metrics"
        }
        response = requests.get(url, headers=self.headers, params=params)
        return response.json().get("data", [])

    def get_tweet_metrics(self, tweet_id):
        """Tweet Statistiken abrufen"""
        url = f"{self.base_url}/tweets/{tweet_id}"
        params = {
            "tweet.fields": "public_metrics",
        }
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
