"""
Notification Service — In-App Benachrichtigungen für den Bot.

Erstellt Benachrichtigungen wenn:
- Just-in-Time Modus: Varianten wurden generiert → Freigabe nötig
- Posts bald fällig aber noch nicht freigegeben
"""
import json, uuid, threading
from datetime import datetime
from pathlib import Path

NOTIF_FILE  = Path("client/notifications.json")
_notif_lock = threading.Lock()


def _load() -> list:
    if NOTIF_FILE.exists():
        try:
            return json.loads(NOTIF_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(notifications: list):
    NOTIF_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Ungelesene immer behalten, gelesene auf max. 80 begrenzen
    unread = [n for n in notifications if not n.get("read")]
    read   = [n for n in notifications if n.get("read")][-80:]
    NOTIF_FILE.write_text(
        json.dumps(unread + read, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def push(
    notif_type: str,
    message: str,
    post_id: str = "",
    platform: str = "",
    scheduled_time: str = "",
    link: str = "/vorschau/woche",
) -> str:
    """Erstellt neue Benachrichtigung. Ignoriert Duplikate für denselben Post."""
    with _notif_lock:
        notifications = _load()
        # Keine doppelten ungelesenen Einträge für denselben Post
        if post_id and any(
            n.get("post_id") == post_id and n.get("type") == notif_type and not n.get("read")
            for n in notifications
        ):
            return ""
        nid = str(uuid.uuid4())[:8]
        notifications.append({
            "id":             nid,
            "type":           notif_type,
            "message":        message,
            "post_id":        post_id,
            "platform":       platform,
            "scheduled_time": scheduled_time,
            "link":           link,
            "created_at":     datetime.now().isoformat(),
            "read":           False,
        })
        _save(notifications)
        return nid


def get_unread() -> list:
    return [n for n in _load() if not n.get("read")]


def get_all(limit: int = 30) -> list:
    return list(reversed(_load()[-limit:]))


def mark_read(nid: str):
    with _notif_lock:
        notifications = _load()
        for n in notifications:
            if n.get("id") == nid:
                n["read"] = True
        _save(notifications)


def mark_all_read():
    with _notif_lock:
        notifications = _load()
        for n in notifications:
            n["read"] = True
        _save(notifications)
