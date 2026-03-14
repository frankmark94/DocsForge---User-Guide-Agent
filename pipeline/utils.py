import base64
import io
import os
import re
import zipfile
from pathlib import Path

import markdown as md


def encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def format_timestamp(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def render_guide_html(guide_markdown: str, image_map: dict[str, str]) -> str:
    html_body = guide_markdown
    for key, b64_data in image_map.items():
        pattern = rf"!\[([^\]]*)\]\({re.escape(key)}\)"
        replacement = (
            f'<img src="data:image/jpeg;base64,{b64_data}" '
            f'alt="\\1" style="max-width:100%;border:1px solid #ddd;'
            f'border-radius:4px;margin:10px 0;" />'
        )
        html_body = re.sub(pattern, replacement, html_body)

    html_body = md.markdown(html_body, extensions=["tables", "fenced_code"])

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6;
         color: #333; }}
  h1 {{ color: #1a1a1a; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
  h2 {{ color: #2c2c2c; margin-top: 30px; }}
  h3 {{ color: #444; }}
  img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; margin: 10px 0;
         display: block; }}
  ol, ul {{ padding-left: 24px; }}
  li {{ margin-bottom: 8px; }}
  blockquote {{ border-left: 4px solid #ddd; margin: 16px 0; padding: 8px 16px;
                color: #666; background: #f9f9f9; }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  @media print {{ body {{ max-width: 100%; }} }}
  @page {{ margin: 2cm; size: A4; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""


def render_guide_for_streamlit(guide_markdown: str, image_map: dict[str, str]) -> str:
    result = guide_markdown
    for key, b64_data in image_map.items():
        pattern = rf"!\[([^\]]*)\]\({re.escape(key)}\)"
        replacement = (
            f'<img src="data:image/jpeg;base64,{b64_data}" '
            f'alt="\\1" style="max-width:100%;border:1px solid #ddd;'
            f'border-radius:4px;margin:10px 0;" />'
        )
        result = re.sub(pattern, replacement, result)
    return result


def generate_pdf_bytes(html_content: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=html_content).write_pdf()


def generate_markdown_zip(
    guide_markdown: str, image_map: dict[str, str], keyframe_paths: list[str]
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        md_content = guide_markdown
        for i, kf_path in enumerate(keyframe_paths):
            key = f"screenshot_{i}"
            filename = f"images/screenshot_{i}.jpg"
            md_content = md_content.replace(f"]({key})", f"]({filename})")
            if os.path.exists(kf_path):
                zf.write(kf_path, filename)

        zf.writestr("user_guide.md", md_content)
    return buf.getvalue()
