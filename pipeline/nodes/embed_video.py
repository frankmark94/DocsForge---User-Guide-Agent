from langsmith import traceable

from pipeline.state import PipelineState
from pipeline.embeddings import create_collection_name, store_embeddings
from pipeline.utils import format_timestamp


@traceable(name="embed_video")
def embed_video_node(state: PipelineState) -> dict:
    video_name = state["video_name"]
    transcript_segments = state.get("transcript_segments", [])
    frame_paths = state.get("frame_paths", [])
    frame_timestamps = state.get("frame_timestamps", [])

    collection_name = create_collection_name(video_name)

    documents = []
    metadatas = []
    ids = []

    # Embed transcript chunks (group into ~30-second windows)
    if transcript_segments:
        window_size = 30.0
        window_start = 0.0
        window_texts = []

        for seg in transcript_segments:
            if seg["start"] >= window_start + window_size and window_texts:
                doc = " ".join(window_texts)
                documents.append(doc)
                metadatas.append({
                    "type": "transcript",
                    "start": window_start,
                    "end": seg["start"],
                })
                ids.append(f"transcript_{window_start:.0f}")
                window_start = seg["start"]
                window_texts = []
            window_texts.append(seg["text"])

        # Final window
        if window_texts:
            end_time = transcript_segments[-1]["end"] if transcript_segments else window_start
            documents.append(" ".join(window_texts))
            metadatas.append({
                "type": "transcript",
                "start": window_start,
                "end": end_time,
            })
            ids.append(f"transcript_{window_start:.0f}")

    # Embed frame descriptions
    for i, (path, ts) in enumerate(zip(frame_paths, frame_timestamps)):
        # Find transcript text near this frame
        nearby_text = ""
        for seg in transcript_segments:
            if abs(seg["start"] - ts) < 5.0 or (seg["start"] <= ts <= seg["end"]):
                nearby_text += " " + seg["text"]

        desc = f"Video frame at {format_timestamp(ts)}"
        if nearby_text.strip():
            desc += f" — narration: {nearby_text.strip()[:200]}"

        documents.append(desc)
        metadatas.append({
            "type": "frame",
            "timestamp": ts,
            "frame_path": path,
        })
        ids.append(f"frame_{i}")

    count = 0
    if documents:
        count = store_embeddings(collection_name, documents, metadatas, ids)

    return {
        "collection_name": collection_name,
        "embedding_count": count,
    }
