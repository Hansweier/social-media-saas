import requests

class LinkedInAPI:
    def __init__(self, access_token):
        self.token = access_token
        self.base_url = "https://api.linkedin.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_profile(self):
        """Eigenes Profil abrufen"""
        url = f"{self.base_url}/me"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def post_text(self, text, person_id):
        """Text-Post veröffentlichen"""
        url = f"{self.base_url}/ugcPosts"
        data = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def post_with_image(self, text, image_url, person_id):
        """Post mit Bild veröffentlichen"""
        url = f"{self.base_url}/ugcPosts"
        data = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "originalUrl": image_url
                    }]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def get_comments(self, post_id):
        """Kommentare eines Posts abrufen"""
        url = f"{self.base_url}/socialActions/{post_id}/comments"
        response = requests.get(url, headers=self.headers)
        return response.json().get("elements", [])

    def reply_to_comment(self, post_id, comment_id, text, person_id):
        """Auf Kommentar antworten"""
        url = f"{self.base_url}/socialActions/{post_id}/comments/{comment_id}/comments"
        data = {
            "actor": f"urn:li:person:{person_id}",
            "message": {"text": text}
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def send_message(self, recipient_id, subject, body, sender_id):
        """LinkedIn Nachricht senden"""
        url = f"{self.base_url}/messages"
        data = {
            "recipients": {
                "values": [{
                    "com.linkedin.voyager.messaging.MessagingMember": {
                        "miniProfile": {"entityUrn": f"urn:li:fs_miniProfile:{recipient_id}"}
                    }
                }]
            },
            "subject": subject,
            "body": body
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()
