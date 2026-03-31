import requests

class InstagramAPI:
    def __init__(self, access_token, account_id):
        self.token = access_token
        self.account_id = account_id
        self.base_url = "https://graph.instagram.com/v18.0"

    def post_image(self, image_url, caption):
        """Bild auf Instagram posten"""
        # Schritt 1: Container erstellen
        container_url = f"{self.base_url}/{self.account_id}/media"
        container_data = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.token
        }
        response = requests.post(container_url, data=container_data)
        container_id = response.json().get("id")

        if not container_id:
            print(f"Fehler beim Erstellen des Containers: {response.json()}")
            return None

        # Schritt 2: Container veröffentlichen
        publish_url = f"{self.base_url}/{self.account_id}/media_publish"
        publish_data = {
            "creation_id": container_id,
            "access_token": self.token
        }
        publish_response = requests.post(publish_url, data=publish_data)
        return publish_response.json()

    def get_comments(self, post_id):
        """Kommentare eines Posts abrufen"""
        url = f"{self.base_url}/{post_id}/comments"
        params = {
            "fields": "id,text,username,timestamp",
            "access_token": self.token
        }
        response = requests.get(url, params=params)
        return response.json().get("data", [])

    def reply_to_comment(self, post_id, message):
        """Auf einen Kommentar antworten"""
        url = f"{self.base_url}/{post_id}/replies"
        data = {
            "message": message,
            "access_token": self.token
        }
        response = requests.post(url, data=data)
        return response.json()

    def get_mentions(self):
        """Mentions des Accounts abrufen"""
        url = f"{self.base_url}/{self.account_id}/tags"
        params = {
            "fields": "id,caption,media_type,timestamp",
            "access_token": self.token
        }
        response = requests.get(url, params=params)
        return response.json().get("data", [])

    def get_messages(self):
        """DMs abrufen (über Messenger API)"""
        url = f"https://graph.facebook.com/v18.0/me/conversations"
        params = {
            "fields": "messages{message,from,created_time}",
            "access_token": self.token,
            "platform": "instagram"
        }
        response = requests.get(url, params=params)
        return response.json().get("data", [])

    def send_message(self, recipient_id, message):
        """DM senden"""
        url = f"https://graph.facebook.com/v18.0/me/messages"
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message},
            "access_token": self.token
        }
        response = requests.post(url, json=data)
        return response.json()
