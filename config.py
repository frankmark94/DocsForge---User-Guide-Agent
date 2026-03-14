import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

# --- LangSmith / LangChain Tracing ---
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGSMITH_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.environ.get("LANGSMITH_PROJECT", "DocsForge")

# --- Frame Extraction ---
FRAME_INTERVAL_SHORT = 2       # seconds between frames for videos < 5 min
FRAME_INTERVAL_LONG = 5        # seconds between frames for videos >= 5 min
VIDEO_SHORT_THRESHOLD = 300    # 5 minutes in seconds
SCENE_CHANGE_THRESHOLD = 30.0  # mean pixel diff for scene change detection
MAX_FRAME_WIDTH = 1280         # resize frames to this max width

# --- Keyframe Selection ---
MAX_KEYFRAMES = 15
MIN_KEYFRAME_SPACING = 3.0     # minimum seconds between selected keyframes
KEYFRAME_BATCH_SIZE = 10       # frames per batch sent to Claude

# --- Models ---
CLAUDE_MODEL = "claude-sonnet-4-20250514"
WHISPER_MODEL = "whisper-1"
EMBEDDING_MODEL = "text-embedding-3-small"

# --- Paths ---
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
FRAMES_DIR = os.path.join(OUTPUT_DIR, "frames")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_store")
