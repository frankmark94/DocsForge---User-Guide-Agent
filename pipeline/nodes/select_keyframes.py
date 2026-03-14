import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langsmith import traceable

from pipeline.state import PipelineState
from pipeline.utils import encode_image_base64, format_timestamp
import config


EVAL_PROMPT = """You are helping create a software user guide from a demo video.
Below are frames extracted from the video along with the transcript of what was
being said at each moment.

For each frame, respond with a JSON array where each element has:
- "index": the frame index (0-based within this batch)
- "importance": integer 1-5 (5 = critical for a user guide)
- "caption": one sentence describing what the screenshot shows

Important frames show: UI state changes, new screens/pages, dialog boxes,
form submissions, menu interactions, button clicks, results/outputs,
error messages, configuration panels.

Unimportant frames show: static/unchanged UI, loading spinners, mouse movement
without interaction, repeated views of the same screen.

TRANSCRIPT CONTEXT:
{transcript_context}

Respond ONLY with the JSON array, no other text."""


@traceable(name="select_keyframes")
def select_keyframes_node(state: PipelineState) -> dict:
    frame_paths = state.get("frame_paths", [])
    frame_timestamps = state.get("frame_timestamps", [])
    transcript_segments = state.get("transcript_segments", [])

    if not frame_paths:
        return {
            "keyframe_paths": [],
            "keyframe_timestamps": [],
            "keyframe_captions": [],
        }

    llm = ChatAnthropic(
        model=config.CLAUDE_MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        max_tokens=4096,
    )

    scored_frames = []

    for batch_start in range(0, len(frame_paths), config.KEYFRAME_BATCH_SIZE):
        batch_end = min(batch_start + config.KEYFRAME_BATCH_SIZE, len(frame_paths))
        batch_paths = frame_paths[batch_start:batch_end]
        batch_timestamps = frame_timestamps[batch_start:batch_end]

        # Build transcript context for this batch
        t_start = batch_timestamps[0] - 5.0
        t_end = batch_timestamps[-1] + 5.0
        context_lines = []
        for seg in transcript_segments:
            if seg["end"] >= t_start and seg["start"] <= t_end:
                context_lines.append(
                    f"[{format_timestamp(seg['start'])}] {seg['text']}"
                )
        transcript_context = "\n".join(context_lines) if context_lines else "(no narration)"

        # Build multimodal message
        content = [
            {"type": "text", "text": EVAL_PROMPT.format(transcript_context=transcript_context)},
        ]
        for i, (path, ts) in enumerate(zip(batch_paths, batch_timestamps)):
            b64 = encode_image_base64(path)
            content.append(
                {"type": "text", "text": f"\n--- Frame {i} at {format_timestamp(ts)} ---"}
            )
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            )

        msg = HumanMessage(content=content)
        response = llm.invoke([msg])

        try:
            evaluations = json.loads(response.content)
            for ev in evaluations:
                idx = batch_start + ev["index"]
                if idx < len(frame_paths):
                    scored_frames.append({
                        "path": frame_paths[idx],
                        "timestamp": frame_timestamps[idx],
                        "importance": ev["importance"],
                        "caption": ev["caption"],
                    })
        except (json.JSONDecodeError, KeyError, TypeError):
            # Fallback: include all batch frames with default score
            for i, (path, ts) in enumerate(zip(batch_paths, batch_timestamps)):
                scored_frames.append({
                    "path": path,
                    "timestamp": ts,
                    "importance": 3,
                    "caption": f"Frame at {format_timestamp(ts)}",
                })

    # Sort by importance descending, then select with spacing constraint
    scored_frames.sort(key=lambda x: x["importance"], reverse=True)
    selected = []
    for frame in scored_frames:
        if len(selected) >= config.MAX_KEYFRAMES:
            break
        too_close = any(
            abs(frame["timestamp"] - s["timestamp"]) < config.MIN_KEYFRAME_SPACING
            for s in selected
        )
        if not too_close:
            selected.append(frame)

    # Sort selected by timestamp for chronological order
    selected.sort(key=lambda x: x["timestamp"])

    return {
        "keyframe_paths": [s["path"] for s in selected],
        "keyframe_timestamps": [s["timestamp"] for s in selected],
        "keyframe_captions": [s["caption"] for s in selected],
    }
