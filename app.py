import base64
import os
import sys
import tempfile
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: E402
from pipeline.graph import build_graph  # noqa: E402
from pipeline.utils import (  # noqa: E402
    render_guide_for_streamlit,
    render_guide_html,
    generate_pdf_bytes,
    generate_markdown_zip,
    encode_image_base64,
)
from history import save_session, list_sessions, load_session, delete_session  # noqa: E402

# ── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DocsForge",
    page_icon=":clipboard:",
    layout="wide",
    initial_sidebar_state="expanded",
)

NODE_LABELS = {
    "extract_audio": ("Extracting audio", "Pulling audio track from video"),
    "extract_frames": ("Extracting frames", "Detecting scenes and capturing frames"),
    "transcribe": ("Transcribing", "Converting speech to text via Whisper"),
    "embed_video": ("Embedding", "Storing vectors in ChromaDB"),
    "select_keyframes": ("Selecting screenshots", "Claude is evaluating frames"),
    "generate_guide": ("Writing guide", "Claude is generating the user guide"),
}

# ── Minimal CSS — only additive, no overrides ────────────────────────────────

st.markdown("""
<style>
    .filmstrip {
        display: flex;
        gap: 6px;
        overflow-x: auto;
        padding: 8px 0 12px 0;
        scrollbar-width: thin;
    }
    .filmstrip img {
        height: 72px;
        width: auto;
        border-radius: 4px;
        border: 1px solid rgba(0,0,0,0.1);
        flex-shrink: 0;
    }
    .transcript-line {
        display: flex;
        gap: 12px;
        padding: 6px 0;
        font-size: 0.88rem;
        border-bottom: 1px solid rgba(0,0,0,0.05);
    }
    .transcript-ts {
        font-family: monospace;
        font-size: 0.78rem;
        color: #b08620;
        min-width: 48px;
        padding-top: 2px;
        font-weight: 500;
    }
    .transcript-text {
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar — History Navigator ──────────────────────────────────────────────

with st.sidebar:
    st.title("DocsForge")
    st.caption("Video to user guide")

    if st.button("+ New Guide", use_container_width=True, type="primary"):
        for key in ["active_session", "guide_md", "image_map",
                     "keyframe_paths", "transcript_segments", "keyframe_captions"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    st.subheader("Previous Guides")

    sessions = list_sessions()
    if sessions:
        for sess in sessions:
            created = datetime.fromtimestamp(sess["created_at"])
            date_str = created.strftime("%b %d, %Y  %I:%M %p")
            video = sess["video_name"]
            is_active = st.session_state.get("active_session") == sess["id"]

            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                label = f":green-background[{video}]" if is_active else video
                if st.button(
                    label,
                    key=f"hist_{sess['id']}",
                    use_container_width=True,
                    help=date_str,
                ):
                    data = load_session(sess["id"])
                    if data:
                        st.session_state["active_session"] = sess["id"]
                        st.session_state["guide_md"] = data["guide_markdown"]
                        st.session_state["image_map"] = data.get("image_map", {})
                        st.session_state["keyframe_paths"] = data.get("keyframe_paths", [])
                        st.session_state["transcript_segments"] = data.get("transcript_segments", [])
                        st.session_state["keyframe_captions"] = data.get("keyframe_captions", [])
                        st.rerun()
            with col_del:
                if st.button(":wastebasket:", key=f"del_{sess['id']}", help="Delete this guide"):
                    delete_session(sess["id"])
                    if st.session_state.get("active_session") == sess["id"]:
                        for key in ["active_session", "guide_md", "image_map",
                                     "keyframe_paths", "transcript_segments", "keyframe_captions"]:
                            st.session_state.pop(key, None)
                    st.rerun()
    else:
        st.caption("No guides yet. Upload a video to get started.")

    st.divider()
    with st.expander("Settings"):
        frame_interval = st.slider(
            "Frame interval (sec)",
            min_value=1, max_value=10, value=2,
            help="Extract one frame every N seconds",
        )
        max_screenshots = st.slider(
            "Max screenshots",
            min_value=5, max_value=20, value=15,
        )
        config.FRAME_INTERVAL_SHORT = frame_interval
        config.MAX_KEYFRAMES = max_screenshots


# ── Main Content ─────────────────────────────────────────────────────────────

has_guide = "guide_md" in st.session_state

if not has_guide:
    # ── Upload State ─────────────────────────────────────────────────────

    st.header("New Guide")
    st.write("Upload a software demo video to generate a step-by-step user guide with screenshots.")

    uploaded_file = st.file_uploader(
        "Upload a software demo video",
        type=["mp4", "avi", "mov", "mkv", "webm"],
        help="Supported formats: MP4, AVI, MOV, MKV, WebM (up to 200MB)",
    )

    if uploaded_file is not None:
        col_preview, col_action = st.columns([3, 1])
        with col_preview:
            st.video(uploaded_file)
        with col_action:
            st.markdown(f"**{uploaded_file.name}**")
            size_mb = uploaded_file.size / (1024 * 1024)
            st.caption(f"{size_mb:.1f} MB")
            generate_btn = st.button(
                "Generate Guide",
                type="primary",
                use_container_width=True,
            )

        if generate_btn:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=os.path.splitext(uploaded_file.name)[1],
            ) as tmp:
                tmp.write(uploaded_file.read())
                video_path = tmp.name

            graph = build_graph()
            accumulated_state = {}

            progress_bar = st.progress(0, text="Starting pipeline...")
            step_count = 0
            total_steps = 6

            for event in graph.stream(
                {"video_path": video_path, "video_name": uploaded_file.name},
                stream_mode="updates",
            ):
                node_name = list(event.keys())[0]
                accumulated_state.update(event[node_name])
                step_count += 1

                if node_name in NODE_LABELS:
                    label, desc = NODE_LABELS[node_name]
                    progress_bar.progress(
                        step_count / total_steps,
                        text=f"Step {step_count}/{total_steps}: {label} — {desc}",
                    )

            progress_bar.progress(1.0, text="Complete!")

            # Clean up temp file
            try:
                os.unlink(video_path)
            except OSError:
                pass

            if accumulated_state.get("guide_markdown"):
                guide_md = accumulated_state["guide_markdown"]
                image_map = accumulated_state.get("guide_image_map", {})
                keyframe_paths = accumulated_state.get("keyframe_paths", [])
                transcript_segments = accumulated_state.get("transcript_segments", [])
                keyframe_captions = accumulated_state.get("keyframe_captions", [])

                session_id = save_session(
                    video_name=uploaded_file.name,
                    guide_markdown=guide_md,
                    image_map=image_map,
                    transcript_segments=transcript_segments,
                    keyframe_paths=keyframe_paths,
                    keyframe_captions=keyframe_captions,
                )

                st.session_state["active_session"] = session_id
                st.session_state["guide_md"] = guide_md
                st.session_state["image_map"] = image_map
                st.session_state["keyframe_paths"] = keyframe_paths
                st.session_state["transcript_segments"] = transcript_segments
                st.session_state["keyframe_captions"] = keyframe_captions
                st.rerun()

else:
    # ── Guide View ───────────────────────────────────────────────────────

    guide_md = st.session_state["guide_md"]
    image_map = st.session_state.get("image_map", {})
    keyframe_paths = st.session_state.get("keyframe_paths", [])
    keyframe_captions = st.session_state.get("keyframe_captions", [])
    transcript_segments = st.session_state.get("transcript_segments", [])

    # ── Filmstrip — keyframe overview ────────────────────────────────────
    filmstrip_imgs = []
    for i, path in enumerate(keyframe_paths):
        alt = keyframe_captions[i] if i < len(keyframe_captions) else f"Screenshot {i+1}"
        if os.path.exists(path):
            b64 = encode_image_base64(path)
            filmstrip_imgs.append(
                f'<img src="data:image/jpeg;base64,{b64}" alt="{alt}" title="{alt}" />'
            )
        elif f"screenshot_{i}" in image_map:
            filmstrip_imgs.append(
                f'<img src="data:image/jpeg;base64,{image_map[f"screenshot_{i}"]}" '
                f'alt="{alt}" title="{alt}" />'
            )

    if filmstrip_imgs:
        st.markdown(
            f'<div class="filmstrip" role="list" aria-label="Key screenshots from video">'
            f'{"".join(filmstrip_imgs)}</div>',
            unsafe_allow_html=True,
        )

    # ── Content Tabs ─────────────────────────────────────────────────────
    tab_guide, tab_transcript, tab_screenshots, tab_artifacts = st.tabs(
        ["User Guide", "Transcript", "Screenshots", "Artifacts"]
    )

    with tab_guide:
        rendered = render_guide_for_streamlit(guide_md, image_map)
        st.markdown(rendered, unsafe_allow_html=True)

    with tab_transcript:
        if transcript_segments:
            for seg in transcript_segments:
                mins = int(seg["start"] // 60)
                secs = int(seg["start"] % 60)
                st.markdown(
                    f'<div class="transcript-line">'
                    f'<span class="transcript-ts">{mins:02d}:{secs:02d}</span>'
                    f'<span class="transcript-text">{seg["text"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No transcript available for this video.")

    with tab_screenshots:
        if keyframe_paths:
            for i in range(0, len(keyframe_paths), 3):
                cols = st.columns(3)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(keyframe_paths):
                        break
                    path = keyframe_paths[idx]
                    caption = keyframe_captions[idx] if idx < len(keyframe_captions) else f"Screenshot {idx + 1}"
                    with col:
                        if os.path.exists(path):
                            st.image(path, caption=caption, use_container_width=True)
                        elif f"screenshot_{idx}" in image_map:
                            img_bytes = base64.b64decode(image_map[f"screenshot_{idx}"])
                            st.image(img_bytes, caption=caption, use_container_width=True)
        else:
            st.info("No screenshots available.")

    with tab_artifacts:
        # Export section
        st.subheader("Export Formats")
        col1, col2, col3 = st.columns(3)

        with col1:
            md_zip = generate_markdown_zip(guide_md, image_map, keyframe_paths)
            st.download_button(
                "Markdown (.zip)",
                data=md_zip,
                file_name="docsforge_guide.zip",
                mime="application/zip",
                use_container_width=True,
            )
            st.caption("Guide + images folder")

        with col2:
            html_content = render_guide_html(guide_md, image_map)
            st.download_button(
                "HTML",
                data=html_content,
                file_name="docsforge_guide.html",
                mime="text/html",
                use_container_width=True,
            )
            st.caption("Self-contained, shareable")

        with col3:
            try:
                html_for_pdf = render_guide_html(guide_md, image_map)
                pdf_bytes = generate_pdf_bytes(html_for_pdf)
                st.download_button(
                    "PDF",
                    data=pdf_bytes,
                    file_name="docsforge_guide.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.caption("Print-ready document")
            except Exception as e:
                st.error(f"PDF generation unavailable: {e}")

        # Raw markdown
        st.divider()
        st.subheader("Raw Markdown")
        with st.expander("View source"):
            st.code(guide_md, language="markdown")

        # Metadata
        st.divider()
        st.subheader("Generation Metadata")
        meta_cols = st.columns(4)
        with meta_cols[0]:
            st.metric("Screenshots", len(keyframe_paths))
        with meta_cols[1]:
            st.metric("Transcript Segments", len(transcript_segments))
        with meta_cols[2]:
            word_count = len(guide_md.split()) if guide_md else 0
            st.metric("Guide Words", f"{word_count:,}")
        with meta_cols[3]:
            st.metric("Images Embedded", len(image_map))
