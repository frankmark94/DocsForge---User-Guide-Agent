import json
import os
import time
from typing import Optional

HISTORY_DIR = os.path.join(os.path.dirname(__file__), "history")


def _ensure_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def save_session(
    video_name: str,
    guide_markdown: str,
    image_map: dict[str, str],
    transcript_segments: list[dict],
    keyframe_paths: list[str],
    keyframe_captions: list[str],
) -> str:
    _ensure_dir()
    session_id = f"{int(time.time())}_{video_name.rsplit('.', 1)[0][:40]}"
    session_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in session_id)

    data = {
        "id": session_id,
        "video_name": video_name,
        "created_at": time.time(),
        "guide_markdown": guide_markdown,
        "image_map": image_map,
        "transcript_segments": transcript_segments,
        "keyframe_paths": keyframe_paths,
        "keyframe_captions": keyframe_captions,
    }

    path = os.path.join(HISTORY_DIR, f"{session_id}.json")
    with open(path, "w") as f:
        json.dump(data, f)

    return session_id


def list_sessions() -> list[dict]:
    _ensure_dir()
    sessions = []
    for fname in os.listdir(HISTORY_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(HISTORY_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            sessions.append({
                "id": data["id"],
                "video_name": data["video_name"],
                "created_at": data["created_at"],
                "path": path,
            })
        except (json.JSONDecodeError, KeyError):
            continue

    sessions.sort(key=lambda x: x["created_at"], reverse=True)
    return sessions


def load_session(session_id: str) -> Optional[dict]:
    _ensure_dir()
    path = os.path.join(HISTORY_DIR, f"{session_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def delete_session(session_id: str) -> bool:
    path = os.path.join(HISTORY_DIR, f"{session_id}.json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
