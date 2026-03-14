from langgraph.graph import StateGraph, START, END

from pipeline.state import PipelineState
from pipeline.nodes.extract_audio import extract_audio_node
from pipeline.nodes.extract_frames import extract_frames_node
from pipeline.nodes.transcribe import transcribe_node
from pipeline.nodes.embed_video import embed_video_node
from pipeline.nodes.select_keyframes import select_keyframes_node
from pipeline.nodes.generate_guide import generate_guide_node


def build_graph() -> StateGraph:
    builder = StateGraph(PipelineState)

    builder.add_node("extract_audio", extract_audio_node)
    builder.add_node("extract_frames", extract_frames_node)
    builder.add_node("transcribe", transcribe_node)
    builder.add_node("embed_video", embed_video_node)
    builder.add_node("select_keyframes", select_keyframes_node)
    builder.add_node("generate_guide", generate_guide_node)

    builder.add_edge(START, "extract_audio")
    builder.add_edge("extract_audio", "extract_frames")
    builder.add_edge("extract_frames", "transcribe")
    builder.add_edge("transcribe", "embed_video")
    builder.add_edge("embed_video", "select_keyframes")
    builder.add_edge("select_keyframes", "generate_guide")
    builder.add_edge("generate_guide", END)

    return builder.compile()
