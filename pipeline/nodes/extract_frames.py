import os

import cv2
from langsmith import traceable

from pipeline.state import PipelineState
import config


@traceable(name="extract_frames")
def extract_frames_node(state: PipelineState) -> dict:
    video_path = state["video_path"]
    os.makedirs(config.FRAMES_DIR, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    interval = (
        config.FRAME_INTERVAL_SHORT
        if duration < config.VIDEO_SHORT_THRESHOLD
        else config.FRAME_INTERVAL_LONG
    )
    interval_frames = int(interval * fps)

    frame_paths = []
    frame_timestamps = []
    prev_gray = None
    frame_idx = 0
    last_saved_ts = -config.MIN_KEYFRAME_SPACING

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / fps
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        should_save = False

        # Save at regular intervals
        if frame_idx % interval_frames == 0:
            should_save = True

        # Save on scene change
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            if diff.mean() > config.SCENE_CHANGE_THRESHOLD:
                should_save = True

        # Enforce minimum spacing
        if should_save and (timestamp - last_saved_ts) >= 1.0:
            # Resize if needed
            h, w = frame.shape[:2]
            if w > config.MAX_FRAME_WIDTH:
                scale = config.MAX_FRAME_WIDTH / w
                frame = cv2.resize(frame, (config.MAX_FRAME_WIDTH, int(h * scale)))

            filename = f"frame_{timestamp:07.2f}s.jpg"
            filepath = os.path.join(config.FRAMES_DIR, filename)
            cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            frame_paths.append(filepath)
            frame_timestamps.append(timestamp)
            last_saved_ts = timestamp

        prev_gray = gray
        frame_idx += 1

    cap.release()

    return {
        "frame_paths": frame_paths,
        "frame_timestamps": frame_timestamps,
    }
