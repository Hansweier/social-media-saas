import requests

class TikTokAPI:
    def __init__(self, access_token):
        self.token = access_token
        self.base_url = "https://open.tiktokapis.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_user_info(self):
        """Eigenes Profil abrufen"""
        url = f"{self.base_url}/user/info/"
        params = {"fields": "open_id,union_id,avatar_url,display_name,follower_count,following_count"}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def upload_video(self, video_path, title, privacy="PUBLIC_TO_EVERYONE"):
        """
        Video auf TikTok hochladen (2-stufiger Prozess)
        Schritt 1: Upload initialisieren
        """
        url = f"{self.base_url}/post/publish/video/init/"
        data = {
            "post_info": {
                "title": title,
                "privacy_level": privacy,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": 0,  # Wird automatisch gesetzt
                "chunk_size": 10000000,
                "total_chunk_count": 1
            }
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def get_videos(self, max_count=10):
        """Eigene Videos abrufen"""
        url = f"{self.base_url}/video/list/"
        data = {
            "max_count": max_count,
            "fields": ["id", "title", "create_time", "like_count", "comment_count", "view_count", "share_count"]
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def get_comments(self, video_id, max_count=20):
        """Kommentare eines Videos abrufen"""
        url = f"{self.base_url}/research/video/comment/list/"
        data = {
            "video_id": video_id,
            "max_count": max_count,
            "fields": ["id", "text", "like_count", "create_time", "username"]
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def get_video_insights(self, video_id):
        """Video-Statistiken abrufen"""
        url = f"{self.base_url}/video/query/"
        data = {
            "filters": {"video_ids": [video_id]},
            "fields": ["like_count", "comment_count", "view_count", "share_count", "play_count"]
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()
