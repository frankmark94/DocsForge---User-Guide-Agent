from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langsmith import traceable

from pipeline.state import PipelineState
from pipeline.utils import encode_image_base64, format_timestamp
import config


GUIDE_PROMPT = """You are a professional technical writer. Create a comprehensive user guide
based on this software demo video. You have the full transcript and key screenshots.

TRANSCRIPT:
{transcript}

SCREENSHOTS (shown as images below, in chronological order):
{screenshot_list}

Write the guide in Markdown format with this structure:
1. A clear, descriptive title (# heading)
2. An overview paragraph explaining what the guide covers
3. Prerequisites section (if apparent from the video)
4. Step-by-step instructions with numbered steps, organized into logical sections (## headings)
5. Insert screenshots at relevant points using this exact syntax: ![caption](screenshot_N)
   where N is the screenshot number (0-based) from the list above
6. Add helpful tips or notes in blockquotes where appropriate
7. A brief summary section at the end

Guidelines:
- Write clear, concise, actionable instructions
- Each step should describe ONE action the user takes
- Reference the screenshots to show what the user should see
- Use the transcript to understand what's being demonstrated
- Include ALL provided screenshots in the guide at appropriate locations
- Do not invent features or steps not shown in the video"""


@traceable(name="generate_guide")
def generate_guide_node(state: PipelineState) -> dict:
    keyframe_paths = state.get("keyframe_paths", [])
    keyframe_timestamps = state.get("keyframe_timestamps", [])
    keyframe_captions = state.get("keyframe_captions", [])
    transcript_segments = state.get("transcript_segments", [])

    # Format transcript
    transcript_lines = []
    for seg in transcript_segments:
        transcript_lines.append(f"[{format_timestamp(seg['start'])}] {seg['text']}")
    transcript_text = "\n".join(transcript_lines) if transcript_lines else "(no audio transcript available)"

    # Format screenshot list
    screenshot_descriptions = []
    for i, (ts, caption) in enumerate(zip(keyframe_timestamps, keyframe_captions)):
        screenshot_descriptions.append(
            f"Screenshot {i} at {format_timestamp(ts)}: {caption}"
        )
    screenshot_list = "\n".join(screenshot_descriptions)

    # Build multimodal message with all keyframes
    content = [
        {
            "type": "text",
            "text": GUIDE_PROMPT.format(
                transcript=transcript_text,
                screenshot_list=screenshot_list,
            ),
        },
    ]

    image_map = {}
    for i, path in enumerate(keyframe_paths):
        b64 = encode_image_base64(path)
        key = f"screenshot_{i}"
        image_map[key] = b64

        content.append(
            {"type": "text", "text": f"\n--- Screenshot {i} ---"}
        )
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        )

    llm = ChatAnthropic(
        model=config.CLAUDE_MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        max_tokens=8192,
    )

    msg = HumanMessage(content=content)
    response = llm.invoke([msg])

    return {
        "guide_markdown": response.content,
        "guide_image_map": image_map,
    }
