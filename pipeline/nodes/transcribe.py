import os
import subprocess

from langsmith import traceable
from openai import OpenAI

from pipeline.state import PipelineState
import config


WHISPER_MAX_SIZE = 25 * 1024 * 1024  # 25 MB


@traceable(name="transcribe")
def transcribe_node(state: PipelineState) -> dict:
    audio_path = state.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        return {"transcript_segments": []}

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    file_size = os.path.getsize(audio_path)

    if file_size <= WHISPER_MAX_SIZE:
        segments = _transcribe_file(client, audio_path)
    else:
        segments = _transcribe_chunked(client, audio_path, file_size)

    return {"transcript_segments": segments}


def _transcribe_file(client: OpenAI, path: str) -> list[dict]:
    with open(path, "rb") as f:
        result = client.audio.transcriptions.create(
            model=config.WHISPER_MODEL,
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    segments = []
    for seg in getattr(result, "segments", []):
        segments.append({
            "start": getattr(seg, "start", 0.0),
            "end": getattr(seg, "end", 0.0),
            "text": getattr(seg, "text", "").strip(),
        })
    return segments


def _transcribe_chunked(
    client: OpenAI, audio_path: str, file_size: int
) -> list[dict]:
    chunk_duration = 600  # 10-minute chunks
    chunk_idx = 0
    offset = 0.0
    all_segments = []
    output_dir = os.path.dirname(audio_path)

    while True:
        chunk_path = os.path.join(output_dir, f"audio_chunk_{chunk_idx}.wav")
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", audio_path,
                    "-ss", str(offset),
                    "-t", str(chunk_duration),
                    "-acodec", "pcm_s16le",
                    "-ar", "16000",
                    "-ac", "1",
                    chunk_path,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0 or not os.path.exists(chunk_path):
                break
            if os.path.getsize(chunk_path) < 1000:
                os.remove(chunk_path)
                break

            segments = _transcribe_file(client, chunk_path)
            for seg in segments:
                seg["start"] += offset
                seg["end"] += offset
            all_segments.extend(segments)

            os.remove(chunk_path)
            offset += chunk_duration
            chunk_idx += 1
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            break

    return all_segments
