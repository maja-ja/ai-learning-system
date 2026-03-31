"""講義 Markdown → 可列印 HTML（含 MathJax / html2pdf，修正重複區塊）"""
from __future__ import annotations

import html as html_module
import re
import time
from typing import Optional

import markdown


def build_printable_html(
    title: str,
    text_content: str,
    img_b64: str = "",
    img_width_percent: int = 80,
    auto_download_pdf: bool = False,
) -> str:
    text_content = (text_content or "").strip()
    processed = text_content.replace("[換頁]", '<div class="manual-page-break"></div>')
    html_body = markdown.markdown(
        processed, extensions=["fenced_code", "tables", "nl2br"]
    )
    date_str = time.strftime("%Y-%m-%d")
    title_esc = html_module.escape(title)
    safe_filename = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_-]+', "_", title)[:80] or "handout"

    img_section = ""
    if img_b64:
        img_section = f"""
        <div class="img-wrapper">
            <img src="data:image/jpeg;base64,{html_module.escape(img_b64)}" style="width:{int(img_width_percent)}%;">
        </div>
        """

    auto_js = (
        "window.onload = function() { setTimeout(downloadPDF, 1000); };"
        if auto_download_pdf
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title_esc}</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Roboto+Mono&display=swap" rel="stylesheet">
    <script>
        window.MathJax = {{
            tex: {{
                inlineMath: [['$', '$']],
                displayMath: [['$$', '$$']],
                processEscapes: true,
                tags: 'ams'
            }},
            chtml: {{ scale: 1.05, displayAlign: 'center' }}
        }};
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <style>
        @page {{ size: A4; margin: 0; }}
        body {{
            font-family: 'Noto Sans TC', sans-serif;
            line-height: 1.75;
            padding: 0; margin: 0;
            background-color: #F3F4F6;
            display: flex; flex-direction: column; align-items: center;
        }}
        #printable-area {{
            background: white;
            width: 210mm;
            min-height: 297mm;
            margin: 30px 0;
            padding: 25mm 25mm;
            box-sizing: border-box;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }}
        .content {{ font-size: 16px; text-align: justify; color: #1F2937; }}
        h1 {{ color: #1E3A8A; text-align: center; font-size: 28px; border-bottom: 2px solid #1E3A8A; padding-bottom: 15px; margin-top: 0; }}
        h2 {{ color: #1E40AF; border-left: 6px solid #3B82F6; padding-left: 12px; margin-top: 35px; margin-bottom: 15px; font-size: 22px; }}
        h3 {{ color: #2563EB; font-weight: 700; margin-top: 25px; margin-bottom: 10px; font-size: 18px; }}
        .img-wrapper {{ text-align: center; margin: 25px 0; }}
        .img-wrapper img {{ border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #E5E7EB; padding: 10px; text-align: left; }}
        th {{ background-color: #F9FAFB; }}
        .manual-page-break {{ page-break-before: always; height: 0; margin: 0; padding: 0; }}
    </style>
</head>
<body>
    <div id="printable-area">
        <h1>{title_esc}</h1>
        <div style="text-align:right; font-size:13px; color:#9CA3AF; margin-bottom: 30px;">
            發佈日期：{date_str} | AI 教育工作站
        </div>
        {img_section}
        <div class="content">{html_body}</div>
    </div>
    <script>
        function downloadPDF() {{
            const element = document.getElementById('printable-area');
            const opt = {{
                margin: 0,
                filename: '{safe_filename}.pdf',
                image: {{ type: 'jpeg', quality: 0.98 }},
                html2canvas: {{ scale: 2, useCORS: true, letterRendering: true, logging: false }},
                jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
            }};
            if (window.MathJax) {{
                MathJax.typesetPromise().then(() => {{
                    html2pdf().set(opt).from(element).save();
                }});
            }} else {{
                html2pdf().set(opt).from(element).save();
            }}
        }}
        {auto_js}
    </script>
</body>
</html>"""
