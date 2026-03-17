import streamlit as st
import pandas as pd
import base64
import time
import json
import re
import random
import os
from io import BytesIO
from PIL import Image, ImageOps
from gtts import gTTS
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import markdown
from supabase import create_client, Client
from pathlib import Path
import zipfile

# Constants
SUPABASE_URL = "https://peupkulfzfbiuiyjzjsd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBldXBrdWxmemZiaXVpeWp6anNkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI0NDc5MjAsImV4cCI6MjA4ODAyMzkyMH0.6Vv7eyK4iN-PLehDoKsbRnvHYPkaUMQ-7KFe8WI8mpg"

CORE_COLS = [
    'word', 'category', 'roots', 'breakdown', 'definition',
    'meaning', 'native_vibe', 'example', 'synonym_nuance',
    'usage_warning', 'memory_hook', 'phonetic'
]

def inject_custom_css():
    css = """
    <style>
    /* ---------- 字體 ---------- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Noto+Sans+TC:wght@400;500;700&display=swap');
    html, body, .stApp {
        font-family: 'Inter','Noto Sans TC',sans-serif;
        background-color:#ffffff;
    }
    /* ---------- 單字主標 ---------- */
    .hero-word{
        font-size:clamp(1.8rem,3vw,2.6rem);
        font-weight:800;
        color:#1A237E;
        letter-spacing:-0.02em;
        margin-bottom:6px;
    }
    /* ---------- 字根拆解卡 ---------- */
    .breakdown-wrapper{
        background:linear-gradient(135deg,#1E3A8A,#2563EB);
        padding:22px;
        border-radius:14px;
        color:white;
        margin:14px 0;
        box-shadow:0 6px 14px rgba(0,0,0,0.08);
    }
    /* ---------- 語感卡 ---------- */
    .vibe-box{
        background:#F8FAFC;
        padding:18px;
        border-radius:12px;
        border-left:5px solid #3B82F6;
        margin:14px 0;
    }
    /* ---------- Navigation ---------- */
    .stRadio div[role="radiogroup"]{
        background:#F1F5F9;
        padding:4px;
        border-radius:12px;
        justify-content:center;
        gap:6px;
    }
    .stRadio div[role="radiogroup"] label{
        padding:8px 18px !important;
        border-radius:8px !important;
        transition:0.2s;
    }
    .stRadio div[role="radiogroup"] label[data-checked="true"]{
        background:white !important;
        box-shadow:0 2px 6px rgba(0,0,0,0.1);
    }
    /* ---------- 手機 ---------- */
    @media (max-width:640px){
        .hero-word{
            font-size:1.6rem;
        }
        .stButton button{
            width:100% !important;
            height:44px;
            border-radius:10px;
        }
        .stMainContainer{
            padding:12px !important;
        }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def get_gemini_keys():
    """
    獲取並隨機打亂 API Keys (支援字串、列表或字串形式的列表)
    優先讀取 GEMINI_FREE_KEYS，若無則讀取 GEMINI_API_KEY
    """
    raw_keys = st.secrets.get("GEMINI_FREE_KEYS") or st.secrets.get("GEMINI_API_KEY")

    if not raw_keys:
        return []

    if isinstance(raw_keys, str):
        if "," in raw_keys:
            keys = [k.strip().replace('"', '').replace("'", "") for k in raw_keys.strip("[]").split(",")]
        else:
            keys = [raw_keys]
    elif isinstance(raw_keys, list):
        keys = raw_keys
    else:
        return []

    valid_keys = [k for k in keys if k and isinstance(k, str)]
    random.shuffle(valid_keys)

    return valid_keys

def fix_content(text):
    """
    優化版內容修復
    """
    if text is None:
        return ""

    text = str(text).strip()

    if text.lower() in ["無", "nan", "", "null", "none"]:
        return ""

    if '\\n' in text:
        text = text.replace('\\n', '\n')

    if '\\\\' in text:
        text = text.replace('\\\\', '\\')

    if len(text) >= 2 and text[0] == text[-1] and text[0] in ['"', "'"]:
        text = text[1:-1]

    lines = text.split('\n')
    processed_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            processed_lines.append("")
            continue

        if line.startswith(('-', '*', '#', '>', '1.', '2.')):
            processed_lines.append(line)
        else:
            processed_lines.append(line + "  ")

    return "\n".join(processed_lines)

@st.cache_data(ttl=60)
def generate_audio_base64(text):
    """
    將 gTTS 生成邏輯獨立出來並加上快取
    """
    if not text: return None

    clean_text = re.sub(r"[^a-zA-Z0-9\s\-\']", " ", str(text))
    clean_text = " ".join(clean_text.split()).strip()

    if not clean_text: return None

    try:
        tts = gTTS(text=clean_text, lang='en')
        fp = BytesIO()
        tts.write_to_fp(fp)
        return base64.b64encode(fp.getvalue()).decode()
    except Exception as e:
        print(f"TTS 生成失敗 ({text}): {e}")
        return None

def speak(text, key_suffix=""):
    """
    TTS 發音生成 (優化版：含快取與錯誤處理)
    """
    audio_base64 = generate_audio_base64(text)

    if not audio_base64:
        return

    unique_id = f"audio_{hash(text)}_{key_suffix}".replace("-", "")

    html_code = f"""
    <html>
    <head>
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; }}
        .btn {{
            background: linear-gradient(to bottom, #ffffff, #f8f9fa);
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 6px 12px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
            font-weight: 500;
            color: #495057;
            transition: all 0.2s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            outline: none;
            user-select: none;
            -webkit-user-select: none;
            width: 100%;
            justify-content: center;
        }}
        .btn:hover {{
            background: #f1f3f5;
            border-color: #ced4da;
            color: #212529;
            transform: translateY(-1px);
        }}
        .btn:active {{
            background: #e9ecef;
            transform: translateY(0);
            box-shadow: none;
        }}
        .btn:focus {{
            box-shadow: 0 0 0 2px rgba(13, 110, 253, 0.25);
            border-color: #86b7fe;
        }}
        .playing {{
            border-color: #86b7fe;
            color: #0d6efd;
            background: #e7f1ff;
        }}
    </style>
    </head>
    <body>
        <button class="btn" id="btn_{unique_id}" onclick="playAudio()">
            <span>🔊</span> 聽發音
        </button>
        <audio id="{unique_id}" style="display:none" preload="none">
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
        </audio>
        <script>
            function playAudio() {{
                var audio = document.getElementById('{unique_id}');
                var btn = document.getElementById('btn_{unique_id}');

                if (audio.paused) {{
                    audio.play();
                    btn.classList.add('playing');
                    btn.innerHTML = '<span>🔊</span> 播放中...';
                }} else {{
                    audio.pause();
                    audio.currentTime = 0;
                    btn.classList.remove('playing');
                    btn.innerHTML = '<span>🔊</span> 聽發音';
                }}

                audio.onended = function() {{
                    btn.classList.remove('playing');
                    btn.innerHTML = '<span>🔊</span> 聽發音';
                }};
            }}
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=45)

def get_spreadsheet_url():
    """
    從 Secrets 獲取 Google Sheets URL
    """
    try:
        return st.secrets["connections"]["gsheets"]["spreadsheet"]
    except KeyError:
        try:
            return st.secrets["gsheets"]["spreadsheet"]
        except KeyError:
            st.error("❌ 未設定 Google Sheets URL，請檢查 .streamlit/secrets.toml")
            return ""

def log_user_intent(label):
    """
    靜默紀錄用戶意願 (Metrics)
    """
    if not label: return

    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        url = get_spreadsheet_url()
        if not url: return

        try:
            m_df = conn.read(spreadsheet=url, worksheet="metrics", ttl=0)
            if 'count' not in m_df.columns:
                m_df['count'] = 0
            m_df['count'] = pd.to_numeric(m_df['count'], errors='coerce').fillna(0).astype(int)
        except Exception:
            m_df = pd.DataFrame(columns=['label', 'count', 'last_updated'])

        current_time = time.strftime("%Y-%m-%d %H:%M:%S")

        if label in m_df['label'].values:
            idx = m_df[m_df['label'] == label].index
            m_df.loc[idx, 'count'] += 1
            m_df.loc[idx, 'last_updated'] = current_time
        else:
            new_record = pd.DataFrame([{
                'label': label,
                'count': 1,
                'last_updated': current_time
            }])
            m_df = pd.concat([m_df, new_record], ignore_index=True)

        conn.update(spreadsheet=url, worksheet="metrics", data=m_df)

    except Exception as e:
        print(f"⚠️ Metrics logging failed for '{label}': {e}")

@st.cache_data(ttl=60)
def load_db():
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        response = supabase.table("knowledge").select("*").order("created_at", desc=True).execute()
        df = pd.DataFrame(response.data)
        df = df.fillna("")

        if df.empty:
            return pd.DataFrame(columns=CORE_COLS)

        return df

    except Exception as e:
        print(f"Supabase Error: {e}")
        return pd.DataFrame(columns=CORE_COLS)

def generate_markdown_note(row):
    """
    將 Supabase row 轉為 Markdown note.md
    """
    return f"""# {row.get('word','')}

## 定義
{fix_content(row.get('definition',''))}

## 本質
{fix_content(row.get('meaning',''))}

## 核心原理
{fix_content(row.get('roots',''))}

## 邏輯拆解
{fix_content(row.get('breakdown',''))}

## 應用
{fix_content(row.get('example',''))}

## 專家理解
{fix_content(row.get('native_vibe',''))}

## 相似概念
{fix_content(row.get('synonym_nuance',''))}

## 注意
{fix_content(row.get('usage_warning',''))}

## 記憶
{fix_content(row.get('memory_hook',''))}

## 詞源
{fix_content(row.get('phonetic',''))}
"""

def export_notes_to_zip(df):
    """
    將知識庫匯出為 Markdown ZIP
    """
    memory_file = BytesIO()

    with zipfile.ZipFile(memory_file, "w") as zf:
        for _, row in df.iterrows():
            word = str(row.get("word","")).strip()
            category = str(row.get("category","其他")).split("+")[0].strip()

            if not word:
                continue

            md = generate_markdown_note(row)
            path = f"知識/{category}/{word}/note.md"
            zf.writestr(path, md)

    memory_file.seek(0)
    return memory_file

def export_notes_to_repo(df):
    """
    將知識庫資料輸出到 GitHub repo 的 知識/ 目錄
    """
    ROOT = Path("知識")
    count = 0

    for _, row in df.iterrows():
        word = str(row.get("word","")).strip()
        category = str(row.get("category","其他")).split("+")[0].strip()

        if not word:
            continue

        folder = ROOT / category / word
        folder.mkdir(parents=True, exist_ok=True)

        md = generate_markdown_note(row)

        with open(folder / "note.md","w",encoding="utf-8") as f:
            f.write(md)

        count += 1

    return count

def submit_report(row_data):
    """
    優化版回報系統：加入時間戳記與狀態標記
    """
    try:
        FEEDBACK_URL = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit?gid=0#gid=0"
        conn = st.connection("gsheets", type=GSheetsConnection)

        if isinstance(row_data, pd.Series):
            report_dict = row_data.to_dict()
        else:
            report_dict = row_data.copy()

        report_dict['report_time'] = time.strftime("%Y-%m-%d %H:%M:%S")
        report_dict['report_status'] = "待處理"

        try:
            existing = conn.read(spreadsheet=FEEDBACK_URL, ttl=0)
        except:
            existing = pd.DataFrame()

        updated = pd.concat([existing, pd.DataFrame([report_dict])], ignore_index=True)
        conn.update(spreadsheet=FEEDBACK_URL, data=updated)

        st.toast(f"🛠️ 已收到「{report_dict.get('word')}」的回報，我們會盡快處理！", icon="✅")
        return True
    except Exception as e:
        st.error(f"❌ 回報發送失敗：{e}")
        return False

def generate_random_topics(primary_cat, aux_cats=[], count=5):
    """
    讓 AI 根據選定領域推薦值得解碼的『繁體中文』主題清單。
    """
    keys = get_gemini_keys()
    if not keys: return ""

    combined_cats = " + ".join([primary_cat] + aux_cats)

    prompt = f"""
    你是一位博學的知識策展人。
    請針對「{combined_cats}」這個領域組合，推薦 {count} 個具備深度學習價值、且能產生有趣跨界洞察的「繁體中文」主題或概念。

    【絕對要求】：
    1. 只輸出主題名稱，每個主題一行。
    2. 必須使用「繁體中文」。
    3. 嚴禁任何開場白、結尾、編號或解釋。
    4. 嚴禁使用任何 Markdown 格式，絕對不能出現「**」或「-」符號。
    5. 嚴禁出現任何標點符號。

    範例輸出：
    熵增定律
    賽局理論
    薪資的起源
    """

    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            if response and response.text:
                clean_text = response.text.replace("*", "").replace("-", "").strip()
                return clean_text
        except:
            continue
    return ""

def ai_decode_and_save(input_text, primary_cat, aux_cats=[]):
    """
    核心解碼函式 (Pro 整合版)
    """
    keys = get_gemini_keys()
    if not keys:
        st.error("❌ 找不到 API Key，請檢查 Secrets 設定。")
        return None

    combined_cats = " + ".join([primary_cat] + aux_cats)

    SYSTEM_PROMPT = f"""
    Role: 全領域知識解構專家 (Interdisciplinary Polymath Decoder).
    Task: 針對輸入內容進行深度拆解，輸出高品質 JSON。

    【核心視角】：
    以「{primary_cat}」為框架，揉合「{', '.join(aux_cats) if aux_cats else '通用百科'}」視角進行交叉解碼。

    【🚫 絕對禁令 - 減少 AI 腔調】：
    - 嚴禁任何開場白或結尾語（如：好的、這是我為您準備的...）。
    - 嚴禁機器人式的過渡句。直接進入知識點，口吻要像冷靜、博學的資深教授。
    - 嚴禁在 JSON 之外輸出任何文字。

    【📐 輸出規範】：
    1. 必須輸出純 JSON 格式，嚴禁包含 ```json 標籤。
    2. LaTeX 雙重轉義：所有 LaTeX 指令必須使用「雙反斜線」。範例："\\\\frac{{a}}{{b}}"。
    3. 換行處理：JSON 內部的換行統一使用 "\\\\n"。

    【📋 欄位定義 (12 核心欄位)】：
    1. word: 核心概念名稱。
    2. category: "{combined_cats}"。
    3. roots: 底層邏輯/核心公式 (LaTeX，不加 $ 符號)。
    4. breakdown: 結構拆解 (3-5 邏輯步驟，用 \\\\n 分隔)。
    5. definition: 直覺定義 (ELI5，不准說「這代表...」，直接說明本質)。
    6. meaning: 本質意義 (一句話點破核心痛點)。
    7. native_vibe: 專家心法 (體現跨領域碰撞出的內行洞察)。
    8. example: 實際應用場景 (優先選擇跨領域案例)。
    9. synonym_nuance: 相似概念辨析。
    10. usage_warning: 邊界條件與誤區。
    11. memory_hook: 記憶金句 (具畫面感的口訣)。
    12. phonetic: 術語發音背景或詞源簡述。
    """

    final_prompt = f"{SYSTEM_PROMPT}\n\n解碼目標：「{input_text}」"

    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')

            response = model.generate_content(
                final_prompt,
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "max_output_tokens": 2048,
                }
            )

            if response and response.text:
                raw_res = response.text
                clean_json = re.sub(r'^```json\s*|\s*```$', '', raw_res.strip(), flags=re.MULTILINE)

                try:
                    parsed_data = json.loads(clean_json, strict=False)

                    for col in CORE_COLS:
                        if col not in parsed_data:
                            parsed_data[col] = "無"

                    parsed_data['category'] = combined_cats

                    return json.dumps(parsed_data, ensure_ascii=False)

                except json.JSONDecodeError as je:
                    try:
                        fixed_json = clean_json.replace('\n', '\\n')
                        return json.dumps(json.loads(fixed_json), ensure_ascii=False)
                    except:
                        print(f"JSON 解析失敗: {je}")
                        continue

        except Exception as e:
            print(f"AI 解碼失敗: {e}")
            continue

    return None

def handout_ai_generate(image, manual_input, instruction):
    """
    Handout AI 核心 (Pro 專業版)：
    1. 嚴格執行去 AI 腔調約束，直接輸出講義內容。
    2. 強化 LaTeX 與 Markdown 的排版安全性。
    3. 支援自動章節換頁標籤。
    """
    keys = get_gemini_keys()
    if not keys: 
        return "❌ 錯誤：未偵測到有效的 API Key。"

    # --- 專業講義架構指令 (去 AI 腔調版) ---
    SYSTEM_PROMPT = """
    Role: 專業教材架構師 (Educational Content Architect).
    Task: 將原始素材轉化為結構嚴謹、排版精美的 A4 講義。
    
    【⚠️ 輸出禁令 - 務必遵守】：
    - **禁止任何開場白與結尾**：嚴禁出現「好的」、「這是我為您準備的」、「希望這份講義對你有幫助」等任何對話式文字。
    - **直接開始**：輸出的第一個字必須是講義標題（# 標題）。
    
    【📐 排版規範】：
    1. **標題層級**：主標題用 #，章節用 ##，重點用 ###。
    2. **行內公式 (Inline Math)**：變數、短公式必須包裹在單個錢字號中，例如：$E=mc^2$。嚴禁在行內使用 $$。
    3. **區塊公式 (Block Math)**：長公式或核心定理必須獨立一行並使用 $$ 包裹，例如：
       $$ \int_{a}^{b} f(x) dx $$
    4. **換頁邏輯**：若內容較長，請在主要章節結束處插入 `[換頁]` 標籤。
    5. **列表格式**：使用標準 Markdown `-` 或 `1.`，確保列表內文字精煉。

    【語氣要求】：
    - 學術、客觀、精確。
    - 減少形容詞，增加動詞與邏輯連接詞。
    """
    
    # 組合輸入素材
    content_parts = [SYSTEM_PROMPT]
    
    if manual_input:
        content_parts.append(f"【原始素材內容】：\n{manual_input}")
    
    if instruction:
        content_parts.append(f"【特定排版要求】：{instruction}")
    
    if image:
        # 確保傳入的是 PIL Image 物件
        content_parts.append("【參考圖片素材】：")
        content_parts.append(image)

    last_error = None
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # 設定生成參數，降低隨機性以確保排版穩定
            generation_config = {
                "temperature": 0.2,
                "top_p": 0.95,
                "max_output_tokens": 4096,
            }
            
            response = model.generate_content(
                content_parts, 
                generation_config=generation_config
            )
            
            if response and response.text:
                # 最終檢查：移除可能殘留的 Markdown 標籤
                final_text = response.text.strip()
                final_text = re.sub(r'^```markdown\s*|\s*```$', '', final_text, flags=re.MULTILINE)
                return final_text
                
        except Exception as e:
            last_error = e
            print(f"⚠️ Key 嘗試失敗: {e}")
            continue
    
    return f"AI 生成中斷。最後錯誤訊息: {str(last_error)}"

def generate_printable_html(title, text_content, img_b64, img_width_percent, auto_download=False):
    """
    專業講義渲染引擎 (Pro 版)：
    1. 支援 MathJax CHTML 高品質公式渲染。
    2. 自動處理 [換頁] 標籤與圖片嵌入。
    3. 整合 PayPal/贊助資訊於講義頁尾。
    """
    # 基礎清理
    text_content = text_content.strip()
    
    # 處理換頁符號：轉換為 CSS 分頁標籤
    processed_content = text_content.replace('[換頁]', '<div class="manual-page-break"></div>')
    
    # Markdown 轉 HTML (支援表格與代碼塊)
    html_body = markdown.markdown(processed_content, extensions=['fenced_code', 'tables', 'nl2br'])
    
    date_str = time.strftime("%Y-%m-%d")
    
    # 圖片區塊處理
    img_section = ""
    if img_b64:
        img_section = f'''
        <div class="img-wrapper">
            <img src="data:image/jpeg;base64,{img_b64}" style="width:{img_width_percent}%;">
        </div>
        '''
    
    # 自動下載腳本
    auto_js = "window.onload = function() { setTimeout(downloadPDF, 1000); };" if auto_download else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Roboto+Mono&display=swap" rel="stylesheet">
        
        <!-- MathJax 3.2.2 CHTML 配置 -->
        <script>
            window.MathJax = {{
                tex: {{ 
                    inlineMath: [['$', '$']], 
                    displayMath: [['$$', '$$']],
                    processEscapes: true,
                    tags: 'ams'
                }},
                chtml: {{ 
                    scale: 1.05,
                    displayAlign: 'center'
                }}
            }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
        
        <!-- html2pdf.js 核心 -->
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
            
            /* A4 紙張模擬 */
            #printable-area {{ 
                background: white; 
                width: 210mm; 
                min-height: 297mm; 
                margin: 30px 0; 
                padding: 25mm 25mm; 
                box-sizing: border-box; 
                position: relative; 
                box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
            }}
            
            /* 內容樣式 */
            .content {{ font-size: 16px; text-align: justify; color: #1F2937; }}
            
            /* 標題設計 */
            h1 {{ color: #1E3A8A; text-align: center; font-size: 28px; border-bottom: 2px solid #1E3A8A; padding-bottom: 15px; margin-top: 0; }}
            h2 {{ color: #1E40AF; border-left: 6px solid #3B82F6; padding-left: 12px; margin-top: 35px; margin-bottom: 15px; font-size: 22px; }}
            h3 {{ color: #2563EB; font-weight: 700; margin-top: 25px; margin-bottom: 10px; font-size: 18px; }}
            
            /* 圖片容器 */
            .img-wrapper {{ text-align: center; margin: 25px 0; }}
            .img-wrapper img {{ border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}

            /* 表格樣式 */
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #E5E7EB; padding: 10px; text-align: left; }}
            th {{ background-color: #F9FAFB; }}

            /* 頁尾贊助資訊 */
            .footer {{ 
                margin-top: 60px; 
                padding-top: 20px; 
                border-top: 1px solid #E5E7EB; 
                text-align: center; 
                font-size: 12px; 
                color: #9CA3AF; 
            }}
            .footer-links {{ margin-top: 5px; font-weight: 500; color: #6B7280; }}

            /* 強制換頁控制 */
            .manual-page-break {{ page-break-before: always; height: 0; margin: 0; padding: 0; }}
            
            /* MathJax 垂直對齊修正 */
            mjx-container[jax="CHTML"][display="false"] {{
                vertical-align: baseline !important;
            }}
        </style>
    </head>
    <body>
        <div id="printable-area">
            <h1>{title}</h1>
            <div style="text-align:right; font-size:13px; color:#9CA3AF; margin-bottom: 30px;">
                發佈日期：{date_str} | AI 教育工作站
            </div>
            
            {img_section}
            
            <div class="content">
                {html_body}
            </div>
            

        <div id="printable-area">
            <h1>{title}</h1>
            <div style="text-align:right; font-size:13px; color:#9CA3AF; margin-bottom: 30px;">
                發佈日期：{date_str} | AI 教育工作站
            </div>
            
            {img_section}
            
            <div class="content">
                {html_body}
            </div>
            

        <script>
            function downloadPDF() {{
                const element = document.getElementById('printable-area');
                const opt = {{
                    margin: 0, 
                    filename: '{title}.pdf', 
                    image: {{ type: 'jpeg', quality: 0.98 }},
                    html2canvas: {{ 
                        scale: 2, 
                        useCORS: true, 
                        letterRendering: true,
                        logging: false
                    }},
                    jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                }};
                
                // 確保 MathJax 渲染完成後再執行轉換
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
    </html>
    """

def get_image_base64(image, max_dim=1200):
    """
    圖片轉 Base64 (優化版)：
    1. 自動縮放：避免高解析度圖片導致 PDF 生成過慢。
    2. 格式轉換：確保相容於 JPEG 格式。
    3. 體積優化：平衡畫質與傳輸速度。
    """
    if image is None: 
        return ""
    
    try:
        # 複製一份避免修改到原始物件
        img = image.copy()
        
        # 效能優化：若圖片長邊超過限制，則等比例縮小
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        buffered = BytesIO()
        # 處理透明背景 (RGBA) 轉為 RGB，避免 JPEG 存檔失敗
        if img.mode in ("RGBA", "P"): 
            img = img.convert("RGB")
            
        # 壓縮品質設為 85 (Pro 級平衡點)，並開啟優化
        img.save(buffered, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        print(f"圖片處理失敗: {e}")
        return ""

def fix_image_orientation(image):
    """
    修正圖片轉向：自動偵測手機拍攝時的 EXIF 資訊並轉正。
    """
    try: 
        image = ImageOps.exif_transpose(image)
    except Exception: 
        pass
    return image