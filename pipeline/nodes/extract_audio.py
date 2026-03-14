import os
import subprocess

from langsmith import traceable

from pipeline.state import PipelineState
import config


@traceable(name="extract_audio")
def extract_audio_node(state: PipelineState) -> dict:
    video_path = state["video_path"]
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    audio_path = os.path.join(config.OUTPUT_DIR, "audio.wav")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                audio_path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            return {"audio_path": audio_path}
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    return {"audio_path": None}
