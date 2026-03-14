from typing import TypedDict, Optional


class PipelineState(TypedDict):
    video_path: str
    video_name: str

    # After extract_audio
    audio_path: Optional[str]

    # After extract_frames
    frame_paths: Optional[list[str]]
    frame_timestamps: Optional[list[float]]

    # After transcribe
    transcript_segments: Optional[list[dict]]

    # After embed_video
    collection_name: Optional[str]
    embedding_count: Optional[int]

    # After select_keyframes
    keyframe_paths: Optional[list[str]]
    keyframe_timestamps: Optional[list[float]]
    keyframe_captions: Optional[list[str]]

    # After generate_guide
    guide_markdown: Optional[str]
    guide_image_map: Optional[dict[str, str]]
