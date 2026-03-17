import streamlit as st
import pandas as pd
import time
import json
import re
import random
import sqlite3
import os
from pathlib import Path
from utils import (
    load_db, generate_random_topics, ai_decode_and_save, fix_content,
    speak, log_user_intent, submit_report, export_notes_to_zip,
    handout_ai_generate, generate_printable_html, get_image_base64,
    fix_image_orientation
)
from exam_db import page_exam_db
from PIL import Image
import streamlit.components.v1 as components

AI_FEATURE_LOCKED = os.getenv("LOCK_AI_FEATURES", "true").strip().lower() in {"1", "true", "yes", "on"}
AI_LOCK_MESSAGE = "🚧 AI 功能暫時鎖定中，講義生成功能優化完成後再開放。"

def show_encyclopedia_card(row):
    """
    最終版百科卡片
    """
    r_word = str(row.get('word', '未命名主題'))
    r_cat = str(row.get('category', '一般'))
    r_phonetic = fix_content(row.get('phonetic', ""))
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_def = fix_content(row.get('definition', ""))
    r_meaning = str(row.get('meaning', ""))
    r_vibe = fix_content(row.get('native_vibe', ""))
    r_ex = fix_content(row.get('example', ""))
    r_nuance = fix_content(row.get('synonym_nuance', ""))
    r_warning = fix_content(row.get('usage_warning', ""))
    r_hook = fix_content(row.get('memory_hook', ""))

    raw_roots = fix_content(row.get('roots', ""))
    clean_roots = raw_roots.replace('$', '').strip()
    r_roots = f"$${clean_roots}$$" if clean_roots and clean_roots != "無" else "*(無公式或原理資料)*"

    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)

    c_sub1, c_sub2 = st.columns([1, 3])
    with c_sub1:
        st.caption(f"🏷️ {r_cat}")
    with c_sub2:
        if r_phonetic and r_phonetic != "無":
            st.caption(f" | /{r_phonetic}/")

    if r_breakdown and r_breakdown != "無":
        st.markdown(f"""
            <div class='breakdown-wrapper'>
                <h4 style='color: white; margin-top: 0; font-size: 1.1rem;'>🧬 結構拆解 / 邏輯步驟</h4>
                <div style='color: white; font-weight: 500; line-height: 1.6;'>{r_breakdown}</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("")

    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        st.markdown("### 🎯 直覺定義 (ELI5)")
        st.write(r_def)
        if r_ex and r_ex != "無":
            st.info(f"💡 **應用實例：**\n{r_ex}")

    with col_right:
        st.markdown("### 💡 核心原理")
        st.markdown(r_roots)
        st.markdown(f"**🔍 本質意義：**\n{r_meaning}")
        if r_hook and r_hook != "無":
            st.markdown(f"**🪝 記憶金句：**\n`{r_hook}`")

    if r_vibe and r_vibe != "無":
        st.markdown(f"""
            <div class='vibe-box'>
                <h4 style='margin-top:0; color: #1E40AF;'>🌊 專家視角 / 跨界洞察</h4>
                {r_vibe}
            </div>
        """, unsafe_allow_html=True)

    with st.expander("🔎 更多細節 (辨析與邊界條件)"):
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.markdown(f"**⚖️ 相似對比：**\n{r_nuance}")
        with sub_c2:
            st.markdown(f"**⚠️ 使用注意：**\n{r_warning}")

    st.write("---")

    op1, op2, op3 = st.columns([1, 1, 1.5])

    with op1:
        speak(r_word, f"card_{r_word}")

    with op2:
        if st.button("🚩 報錯/建議", key=f"rep_{r_word}", use_container_width=True):
            submit_report(row)

    with op3:
        if st.button("📄 生成專題講義", key=f"jump_ho_{r_word}", type="primary", use_container_width=True):
            log_user_intent(f"handout_{r_word}")

            inherited_draft = f"""# 專題講義：{r_word}
領域：{r_cat}
## 🧬 邏輯結構
{r_breakdown}
## 🎯 核心定義 (ELI5)
{r_def}
## 💡 科學原理/底層邏輯
{r_roots}
**本質意義**：{r_meaning}
---
## 🚀 應用實例
{r_ex}
## 🌊 專家心法
{r_vibe}
---
**💡 記憶秘訣**：{r_hook}
"""
            st.session_state.manual_input_content = inherited_draft
            st.session_state.preview_editor = inherited_draft
            st.session_state.final_handout_title = f"{r_word} 專題講義"
            st.session_state.app_mode = "📄 講義排版"
            st.rerun()

def page_etymon_lab():
    """
    🔬 跨領域批量解碼實驗室
    """
    st.title("🔬 跨領域解碼實驗室")
    st.caption("輸入多個主題並選擇領域視角，系統將進行深度邏輯拆解並自動同步至雲端 Sheet2。")

    if AI_FEATURE_LOCKED:
        st.warning(AI_LOCK_MESSAGE)

    CORE_COLS = [
        'word', 'category', 'roots', 'breakdown', 'definition',
        'meaning', 'native_vibe', 'example', 'synonym_nuance',
        'usage_warning', 'memory_hook', 'phonetic'
    ]

    CATEGORIES = {
        "語言與邏輯": ["英語辭源", "語言邏輯", "符號學", "修辭學"],
        "科學與技術": ["物理科學", "生物醫學", "神經科學", "量子力學", "人工智慧", "數學邏輯"],
        "人文與社會": ["歷史文明", "政治法律", "社會心理", "哲學宗教", "軍事戰略", "古希臘神話", "考古發現"],
        "商業與職場": ["商業商戰", "金融投資", "產品設計", "數位行銷", "職場政治", "管理學", "賽局理論"],
        "生活與藝術": ["餐飲文化", "社交禮儀", "藝術美學", "影視文學", "運動健身", "流行文化", "心理療癒"]
    }
    FLAT_CATEGORIES = [item for sublist in CATEGORIES.values() for item in sublist]

    with st.container(border=True):
        col_cat1, col_cat2 = st.columns(2)
        with col_cat1:
            primary_cat = st.selectbox("🎯 主核心領域", FLAT_CATEGORIES, index=0)
        with col_cat2:
            aux_cats = st.multiselect("🧩 輔助分析視角", FLAT_CATEGORIES, help="選擇輔助領域進行交叉分析")

        display_category = primary_cat + (" + " + " + ".join(aux_cats) if aux_cats else "")
        st.markdown(f"**當前解碼視角：** `{display_category}`")

    st.write("")

    if 'batch_input_area' not in st.session_state:
        st.session_state['batch_input_area'] = ""

    col_input_h, col_gen_h = st.columns([3, 1])
    with col_input_h:
        st.markdown("**📝 待解碼主題清單** (每行一個概念)")
    with col_gen_h:
        if st.button("🎲 隨機靈感", use_container_width=True, help="讓 AI 推薦 5 個中文主題", disabled=AI_FEATURE_LOCKED):
            with st.spinner("正在策展中文主題..."):
                random_topics = generate_random_topics(primary_cat, aux_cats, count=5)
                if random_topics:
                    st.session_state['batch_input_area'] = random_topics
                    st.rerun()

    raw_input = st.text_area(
        "主題輸入區域",
        key="batch_input_area",
        placeholder="例如：\n熵增定律\n薪資的起源\n賽局理論",
        height=180,
        label_visibility="collapsed"
    )

    with st.expander("⚙️ 批量處理參數"):
        force_refresh = st.checkbox("🔄 強制刷新 (覆蓋 Sheet2 已存在的資料)")
        delay_sec = st.slider("API 請求間隔 (秒)", 0.5, 3.0, 1.0)

    st.write("---")

    if st.button("🚀 啟動批量深度解碼", type="primary", use_container_width=True, disabled=AI_FEATURE_LOCKED):
        if AI_FEATURE_LOCKED:
            st.error(AI_LOCK_MESSAGE)
            return

        input_list = [w.strip() for w in re.split(r'[\n,，]', raw_input) if w.strip()]

        if not input_list:
            st.warning("請先輸入或生成主題清單。")
            return

        # 本機 SQLite 設定
        DB_PATH = Path("streamlit_app/data/local_sheet2.db")
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 建立連線，允許跨 thread，timeout 增加以避免短暫鎖定失敗
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")

        # 建表（word 當主鍵）
        cols_sql = ", ".join(f"{c} TEXT" for c in CORE_COLS if c != "word")
        create_sql = f"CREATE TABLE IF NOT EXISTS sheet2 (word TEXT PRIMARY KEY, {cols_sql})"
        conn.execute(create_sql)
        conn.commit()

        # 讀取成 DataFrame
        try:
            existing_data = pd.read_sql_query("SELECT * FROM sheet2", conn)
        except Exception:
            existing_data = pd.DataFrame(columns=CORE_COLS)

        new_records = []
        total = len(input_list)
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, word in enumerate(input_list):
            status_text.markdown(f"⏳ **正在處理 ({i+1}/{total}):** `{word}`")

            is_exist = False
            if not existing_data.empty:
                is_exist = (existing_data['word'].astype(str).str.lower() == word.lower().strip()).any()

            if is_exist and not force_refresh:
                status_text.markdown(f"⏩ **跳過已存在項目:** `{word}`")
            else:
                raw_res = ai_decode_and_save(word, primary_cat, aux_cats)

                if raw_res:
                    try:
                        res_data = json.loads(raw_res)
                        row = {col: res_data.get(col, "無") for col in CORE_COLS}
                        row['category'] = display_category
                        new_records.append(row)
                    except:
                        st.error(f"❌ `{word}` 解析失敗")

                time.sleep(delay_sec)

            progress_bar.progress((i + 1) / total)

        if new_records:
            status_text.markdown("💾 **正在同步至本機資料庫...**")
            new_df = pd.DataFrame(new_records)
            if force_refresh and not existing_data.empty:
                new_words_lower = [r['word'].lower().strip() for r in new_records]
                existing_data = existing_data[~existing_data['word'].str.lower().str.strip().isin(new_words_lower)]

            updated_df = pd.concat([existing_data, new_df], ignore_index=True)[CORE_COLS]

            # 將資料寫入 SQLite
            cur = conn.cursor()
            for _, row in updated_df.iterrows():
                vals = [row.get(c, "") for c in CORE_COLS]
                placeholders = ", ".join("?" for _ in CORE_COLS)
                cols = ", ".join(CORE_COLS)
                sql = f"INSERT OR REPLACE INTO sheet2 ({cols}) VALUES ({placeholders})"
                cur.execute(sql, vals)
            conn.commit()

            st.success(f"🎉 批量處理完成！成功同步 {len(new_records)} 筆資料至本機資料庫。")
            st.balloons()

            with st.expander("📝 查看本次生成結果摘要", expanded=True):
                st.table(new_df[['word', 'category', 'definition']])
        else:
            st.info("清單中的主題已存在，且未開啟強制刷新。")

        status_text.empty()
        conn.close()

def page_etymon_home(df):
    """
    Etymon Decoder 門戶首頁
    """
    st.write("")

    if st.button("📚 匯出 Markdown 知識庫"):
        with st.spinner("正在生成 Markdown..."):
            zip_bytes = export_notes_to_zip(df)

        st.download_button(
            "⬇️ 下載 Markdown 知識庫",
            data=zip_bytes,
            file_name="knowledge_markdown.zip",
            mime="application/zip",
            use_container_width=True
        )

    st.markdown("<h1 style='text-align: center; color: #1A237E;'>Etymon Decoder</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748B; font-size: 1.1rem;'>深度知識解構與跨領域邏輯圖書館</p>", unsafe_allow_html=True)
    st.write("---")

    if not df.empty:
        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric("📚 知識庫總量", f"{len(df)} 筆")

        with c2:
            st.metric("🏷️ 涵蓋領域", f"{df['category'].nunique()} 類")

        with c3:
            unique_roots = df['roots'].nunique()
            st.metric("🧬 核心邏輯", f"{unique_roots} 組")

    else:
        st.info("目前資料庫尚無資料，請前往實驗室進行首次解碼。")
        return

    st.write("")

    col_h, col_btn = st.columns([4,1])

    with col_h:
        st.subheader("💡 今日隨機啟發")

    with col_btn:
        if st.button("🔄 換一批", use_container_width=True):
            if 'home_sample' in st.session_state:
                del st.session_state.home_sample
            st.rerun()

    if 'home_sample' not in st.session_state:
        st.session_state.home_sample = df.sample(min(3,len(df)))

    sample = st.session_state.home_sample
    cols = st.columns(3)

    for i,(index,row) in enumerate(sample.iterrows()):
        with cols[i%3]:
            with st.container(border=True):
                st.markdown(f"### {row['word']}")
                st.caption(f"🏷️ {row['category']}")

                meaning_text = fix_content(row['meaning'])
                if len(meaning_text) > 45:
                    meaning_text = meaning_text[:45] + "..."

                st.markdown(f"**本質：**\n{meaning_text}")

                st.write("")

                b_col1,b_col2 = st.columns(2)

                with b_col1:
                    speak(row['word'],f"home_{i}")

                with b_col2:
                    if st.button("🚩 有誤",key=f"h_rep_{i}_{row['word']}",use_container_width=True):
                        submit_report(row)

                if st.button(
                    "🔍 查看詳情",
                    key=f"h_det_{i}_{row['word']}",
                    type="primary",
                    use_container_width=True
                ):
                    st.session_state.curr_w = row.to_dict()
                    st.session_state.etymon_page = "📖 學習搜尋"
                    st.session_state.back_to = "🏠 首頁概覽"
                    st.rerun()

    st.write("---")

    st.markdown("""
        <div style='text-align: center; color: #94A3B8; font-size: 0.9rem;'>
            👈 提示：點擊頂部「📖 學習搜尋」可查看完整清單。
        </div>
    """, unsafe_allow_html=True)

def page_etymon_learn(df):
    """
    知識庫探索
    """
    if df is None or df.empty or 'category' not in df.columns:
        st.warning("資料庫尚未建立或沒有資料")
        return

    if st.session_state.get("back_to"):
        col_back, _ = st.columns([1, 2])
        with col_back:
            if st.button(f"⬅️ 返回{st.session_state.back_to}", use_container_width=True):
                target = st.session_state.back_to
                st.session_state.back_to = None
                st.session_state.curr_w = None
                st.session_state.etymon_page = target
                st.rerun()

    if st.session_state.get('curr_w'):
        show_encyclopedia_card(st.session_state.curr_w)

        st.write("")
        if st.button("🔍 關閉詳情，回到搜尋列表", use_container_width=True):
            st.session_state.curr_w = None
            st.rerun()

    else:
        tab_explore, tab_search = st.tabs(["🎲 隨機探索", "🔍 搜尋與列表"])

        with tab_explore:
            col_cat, col_btn = st.columns([2, 1])
            with col_cat:
                cats = ["全部領域"] + sorted(df.get('category', pd.Series()).dropna().unique().tolist())
                sel_cat = st.selectbox("選擇學習領域", cats, key="explore_cat_sel")

            with col_btn:
                st.write("")
                if st.button("🎲 抽下一個", use_container_width=True, type="primary"):
                    f_df = df if sel_cat == "全部領域" else df[df['category'] == sel_cat]
                    if not f_df.empty:
                        st.session_state.curr_w = f_df.sample(1).iloc[0].to_dict()
                        st.session_state.back_to = "📖 學習搜尋"
                    else:
                        st.session_state.curr_w = None
                    st.rerun()

            if not st.session_state.get('curr_w'):
                st.info("請點擊「🎲 抽下一個」開始探索，或切換至「🔍 搜尋與列表」進行查找。")

        with tab_search:
            col_input, col_cat_filter = st.columns([2, 1])

            with col_input:
                search_query = st.text_input("🔍 關鍵字搜尋", placeholder="輸入單字、定義或本質意義...", key="search_input")

            with col_cat_filter:
                cats_for_search = ["所有領域"] + sorted(
    df['category'].fillna("").unique().tolist()
)
                sel_cat_search = st.selectbox("篩選領域", cats_for_search, key="search_cat_selector")

            base_df_for_display = df if sel_cat_search == "所有領域" else df[df['category'] == sel_cat_search]

            if search_query:
                q = search_query.strip().lower()
                mask = (
                    base_df_for_display['word'].str.contains(q, case=False, na=False) |
                    base_df_for_display['definition'].str.contains(q, case=False, na=False) |
                    base_df_for_display['category'].str.contains(q, case=False, na=False) |
                    base_df_for_display['meaning'].str.contains(q, case=False, na=False)
                )

                res_df = base_df_for_display[mask]

                if not res_df.empty:
                    st.success(f"在「{sel_cat_search}」中找到 {len(res_df)} 筆結果：")
                    for _, row in res_df.iterrows():
                        with st.container(border=True):
                            st.markdown(f"**{row['word']}** ( {row['category']} )")
                            meaning_prev = fix_content(row['meaning'])
                            st.caption(f"{meaning_prev[:80]}...")
                            if st.button("查看完整詳情", key=f"search_det_{row['word']}", use_container_width=True):
                                st.session_state.curr_w = row.to_dict()
                                st.session_state.back_to = "📖 學習搜尋"
                                st.rerun()
                else:
                    st.error(f"在「{sel_cat_search}」中找不到與「{search_query}」相關的內容。")
            else:
                st.write(f"### 📚 「{sel_cat_search}」 知識清單")
                st.dataframe(
                    base_df_for_display[['word', 'category', 'meaning']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "word": "主題",
                        "category": "領域視角",
                        "meaning": "本質意義"
                    }
                )

def run_handout_app():
    """
    講義排版應用 - 大優化版本
    """
    col_back, col_space = st.columns([1, 4])
    with col_back:
        if st.button("⬅️ 返回單字解碼", use_container_width=True):
            st.session_state.app_mode = "🔬 單字解碼"
            st.rerun()

    st.header("🎓 AI 講義排版大師 Pro")
    st.caption("將混亂的題目圖片或筆記素材，轉化為結構嚴謹、排版精美的 A4 教材。")

    if AI_FEATURE_LOCKED:
        st.warning(AI_LOCK_MESSAGE)

    is_admin = st.session_state.get("is_admin", False)

    # 初始化 session state
    if "manual_input_content" not in st.session_state:
        st.session_state.manual_input_content = ""
    if "rotate_angle" not in st.session_state:
        st.session_state.rotate_angle = 0
    if "preview_editor" not in st.session_state:
        st.session_state.preview_editor = ""
    if "final_handout_title" not in st.session_state:
        st.session_state.final_handout_title = "專題講義"
    if "trigger_download" not in st.session_state:
        st.session_state.trigger_download = False
    if "selected_template" not in st.session_state:
        st.session_state.selected_template = "standard"
    if "batch_files" not in st.session_state:
        st.session_state.batch_files = []
    if "handout_history" not in st.session_state:
        st.session_state.handout_history = []

    # 載入模板
    templates_dir = Path("streamlit_app/templates")
    templates = {}
    if templates_dir.exists():
        for template_file in templates_dir.glob("*.md"):
            template_name = template_file.stem
            with open(template_file, 'r', encoding='utf-8') as f:
                templates[template_name] = f.read()

    # 主標籤頁
    tab_single, tab_batch, tab_history = st.tabs(["📄 單一講義", "📚 批量處理", "📖 歷史記錄"])

    with tab_single:
        run_single_handout_app(is_admin, templates)

    with tab_batch:
        run_batch_handout_app(is_admin, templates)

    with tab_history:
        run_handout_history_app()

def run_single_handout_app(is_admin, templates):
    """單一講義處理"""
    col_ctrl, col_prev = st.columns([1, 1.4], gap="large")

    with col_ctrl:
        st.subheader("1. 素材準備")

        # 模板選擇
        if templates:
            template_options = ["自訂內容"] + list(templates.keys())
            selected_template = st.selectbox(
                "📋 選擇講義模板",
                template_options,
                index=0,
                help="選擇預設模板快速開始，或選擇自訂內容"
            )

            if selected_template != "自訂內容":
                if st.button("📋 套用模板", use_container_width=True):
                    st.session_state.manual_input_content = templates[selected_template]
                    st.session_state.selected_template = selected_template
                    st.rerun()

        uploaded_file = st.file_uploader("📷 上傳題目或筆記照片 (可選)", type=["jpg", "png", "jpeg"])
        image_obj = None
        img_width = 80

        if uploaded_file:
            raw_img = Image.open(uploaded_file)
            image_obj = fix_image_orientation(raw_img)

            if st.session_state.rotate_angle != 0:
                image_obj = image_obj.rotate(-st.session_state.rotate_angle, expand=True)

            c1, c2 = st.columns([1, 2])
            with c1:
                if st.button("🔄 旋轉 90°"):
                    st.session_state.rotate_angle = (st.session_state.rotate_angle + 90) % 360
                    st.rerun()
            with c2:
                img_width = st.slider("圖片顯示寬度 (%)", 10, 100, 80)

            st.image(image_obj, use_container_width=True, caption="素材預覽")

        st.divider()

        st.markdown("**📝 講義原始素材**")
        st.text_area(
            "請輸入欲排版的文字內容、題目或知識點：",
            key="manual_input_content",
            height=250,
            placeholder="在此貼上從解碼實驗室複製的內容，或手打筆記..."
        )

        if is_admin:
            with st.expander("🛠️ AI 結構化排版 (管理員專用)", expanded=True):
                if AI_FEATURE_LOCKED:
                    st.info("目前僅保留手動編輯與排版預覽，AI 生成暫時停用。")

                ENHANCED_STYLES = {
                    "📘 標準教科書": "【要求】：標題使用#，變數用$x$，長公式用$$，嚴禁純LaTeX指令。包含學習目標、核心內容、練習題、總結。",
                    "📝 試卷解析模式": "【要求】：結構分為題目、解析、答案，選項用(A)(B)(C)(D)。包含詳解和常見錯誤分析。",
                    "💡 知識百科模式": "【要求】：強調定義、原理與應用實例，使用豐富的 Markdown 標記。包含跨領域聯想。",
                    "🔬 研究報告": "【要求】：引言、理論基礎、詳細分析、實證研究、結論與展望。包含參考資料。",
                    "🎯 互動學習": "【要求】：學習目標清單、核心概念、互動練習、自我評估、延伸閱讀。",
                    "📊 數據分析": "【要求】：問題定義、數據收集、分析方法、結果解釋、建議。"
                }

                col_style, col_instr = st.columns([1, 1])
                with col_style:
                    selected_style = st.selectbox("選擇排版風格", list(ENHANCED_STYLES.keys()))
                with col_instr:
                    user_instr = st.text_input("補充指令", placeholder="例如：加入練習題、強調重點...")

                col_gen, col_clear = st.columns(2)
                with col_gen:
                    if st.button("🚀 執行結構化生成", type="primary", use_container_width=True, disabled=AI_FEATURE_LOCKED):
                        with st.spinner("正在優化講義架構..."):
                            final_instruction = f"{ENHANCED_STYLES[selected_style]}\n{user_instr}"
                            generated_res = handout_ai_generate(image_obj, st.session_state.manual_input_content, final_instruction)

                            st.session_state.preview_editor = generated_res

                            for line in generated_res.split('\n'):
                                clean_t = line.replace('#', '').strip()
                                if clean_t:
                                    st.session_state.final_handout_title = clean_t
                                    break
                            st.rerun()

                with col_clear:
                    if st.button("🗑️ 清空內容", use_container_width=True):
                        st.session_state.manual_input_content = ""
                        st.session_state.preview_editor = ""
                        st.session_state.final_handout_title = "專題講義"
                        st.rerun()
        else:
            st.info("💡 提示：您可以直接在右側編輯器中貼上內容進行排版。AI 自動排版功能目前僅開放給管理員。")

    with col_prev:
        st.subheader("2. A4 預覽與修訂")

        c_title, c_dl = st.columns([2, 1])
        with c_title:
            st.session_state.final_handout_title = st.text_input(
                "講義標題",
                value=st.session_state.final_handout_title,
                placeholder="請輸入 PDF 檔名..."
            )
        with c_dl:
            st.write("")
            if st.button("📥 下載 PDF", type="primary", use_container_width=True):
                log_user_intent(f"pdf_dl_{st.session_state.final_handout_title}")
                st.session_state.trigger_download = True

                # 保存到歷史記錄
                handout_record = {
                    "title": st.session_state.final_handout_title,
                    "content": st.session_state.preview_editor,
                    "timestamp": time.time(),
                    "template": st.session_state.get("selected_template", "custom")
                }
                st.session_state.handout_history.insert(0, handout_record)
                if len(st.session_state.handout_history) > 50:  # 保留最近50個
                    st.session_state.handout_history = st.session_state.handout_history[:50]

                st.rerun()

        st.caption("💖 講義下載完全免費。若覺得好用，歡迎透過側邊欄贊助支持 AI 算力支出。")

        if not st.session_state.preview_editor and st.session_state.manual_input_content:
             st.session_state.preview_editor = st.session_state.manual_input_content

        edited_content = st.text_area(
            "📝 內容修訂 (支援 Markdown 與 LaTeX)",
            key="preview_editor",
            height=450,
            help="您可以在此直接修改 AI 生成的內容。使用 $...$ 包裹行內公式，$$...$$ 包裹區塊公式。"
        )

        with st.container(border=True):
            st.markdown("**📄 A4 即時預覽 (模擬下載效果)**")

            img_b64 = get_image_base64(image_obj) if image_obj else ""

            final_html = generate_printable_html(
                title=st.session_state.final_handout_title,
                text_content=edited_content,
                img_b64=img_b64,
                img_width_percent=img_width,
                auto_download=st.session_state.trigger_download
            )

            components.html(final_html, height=850, scrolling=True)

        if st.session_state.trigger_download:
            st.session_state.trigger_download = False

def run_batch_handout_app(is_admin, templates):
    """批量講義處理"""
    st.subheader("📚 批量講義處理")

    if AI_FEATURE_LOCKED:
        st.info("目前暫停批量 AI 生成，可先使用「單一講義」手動整理內容。")

    st.markdown("""
    批量處理多個圖片或文本內容，自動生成結構化的講義集合。
    適用於：試卷批次處理、課程筆記整理、多主題學習材料製作。
    """)

    # 批量文件上傳
    uploaded_files = st.file_uploader(
        "📎 上傳多個圖片文件",
        type=["jpg", "png", "jpeg"],
        accept_multiple_files=True,
        help="支援同時上傳多個圖片文件"
    )

    if uploaded_files:
        st.success(f"已上傳 {len(uploaded_files)} 個文件")

        # 顯示文件預覽
        cols = st.columns(min(4, len(uploaded_files)))
        for i, file in enumerate(uploaded_files):
            with cols[i % 4]:
                img = Image.open(file)
                img = fix_image_orientation(img)
                st.image(img, caption=f"{file.name}", width=150)

    # 批量文本輸入
    st.divider()
    st.markdown("**📝 批量文本內容**")
    batch_text = st.text_area(
        "輸入多個主題內容（每行一個主題，或用---分隔）",
        height=200,
        placeholder="主題1內容...\n---\n主題2內容...\n---\n主題3內容..."
    )

    # 處理參數
    with st.expander("⚙️ 批量處理參數"):
        col1, col2 = st.columns(2)
        with col1:
            batch_template = st.selectbox(
                "統一模板",
                ["自訂"] + list(templates.keys()) if templates else ["自訂"],
                help="為所有講義應用相同模板"
            )
            batch_style = st.selectbox(
                "AI 排版風格",
                ["📘 標準教科書", "📝 試卷解析模式", "💡 知識百科模式", "🔬 研究報告"],
                help="選擇 AI 結構化風格"
            )
        with col2:
            combine_output = st.checkbox("合併為單一 PDF", value=True, help="將所有講義合併為一個 PDF 文件")
            add_page_breaks = st.checkbox("添加分頁符", value=True, help="在每個講義間添加分頁")

    if st.button("🚀 開始批量處理", type="primary", use_container_width=True, disabled=AI_FEATURE_LOCKED):
        if AI_FEATURE_LOCKED:
            st.error(AI_LOCK_MESSAGE)
            return

        if not uploaded_files and not batch_text.strip():
            st.error("請上傳圖片文件或輸入文本內容")
            return

        with st.spinner("正在批量處理講義..."):
            progress_bar = st.progress(0)
            status_text = st.empty()

            batch_results = []

            # 處理圖片文件
            if uploaded_files:
                for i, file in enumerate(uploaded_files):
                    status_text.text(f"處理圖片 {i+1}/{len(uploaded_files)}: {file.name}")
                    img = Image.open(file)
                    img = fix_image_orientation(img)

                    # AI 生成內容
                    instruction = f"從圖片中提取內容並按{st.session_state.get('batch_style', '標準教科書')}風格排版"
                    generated_content = handout_ai_generate(img, "", instruction)

                    batch_results.append({
                        "title": file.name.replace('.jpg', '').replace('.png', '').replace('.jpeg', ''),
                        "content": generated_content,
                        "source": "image",
                        "filename": file.name
                    })

                    progress_bar.progress((i + 1) / (len(uploaded_files) + (1 if batch_text.strip() else 0)))

            # 處理文本內容
            if batch_text.strip():
                text_sections = batch_text.split('---')
                for i, section in enumerate(text_sections):
                    if section.strip():
                        status_text.text(f"處理文本段落 {i+1}/{len(text_sections)}")
                        instruction = f"按{st.session_state.get('batch_style', '標準教科書')}風格排版以下內容"
                        generated_content = handout_ai_generate(None, section.strip(), instruction)

                        batch_results.append({
                            "title": f"主題 {i+1}",
                            "content": generated_content,
                            "source": "text",
                            "section": i + 1
                        })

                if uploaded_files:
                    progress_bar.progress(1.0)
                else:
                    progress_bar.progress((len(text_sections)) / len(text_sections))

            status_text.empty()
            progress_bar.empty()

            if batch_results:
                st.success(f"批量處理完成！生成了 {len(batch_results)} 份講義")

                # 顯示結果摘要
                with st.expander("📋 處理結果摘要", expanded=True):
                    for i, result in enumerate(batch_results):
                        st.markdown(f"**{i+1}. {result['title']}**")
                        st.caption(f"來源: {result['source']} | 內容長度: {len(result['content'])} 字")
                        if i < 3:  # 只顯示前3個的預覽
                            st.text_area(f"內容預覽 {i+1}", result['content'][:200] + "...", height=100, disabled=True)

                # 下載選項
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📥 下載合併 PDF", type="primary", use_container_width=True):
                        # TODO: 實現合併 PDF 下載
                        st.info("合併 PDF 功能開發中...")

                with col2:
                    if st.button("📦 分別下載", use_container_width=True):
                        # TODO: 實現分開下載
                        st.info("分開下載功能開發中...")

                # 保存到歷史記錄
                for result in batch_results:
                    handout_record = {
                        "title": result["title"],
                        "content": result["content"],
                        "timestamp": time.time(),
                        "template": "batch",
                        "batch_info": f"{len(batch_results)}份講義中的一份"
                    }
                    st.session_state.handout_history.insert(0, handout_record)

def run_handout_history_app():
    """講義歷史記錄"""
    st.subheader("📖 講義歷史記錄")

    if not st.session_state.handout_history:
        st.info("尚無講義歷史記錄")
        return

    # 歷史記錄列表
    for i, record in enumerate(st.session_state.handout_history):
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"**{record['title']}**")
                timestamp = time.strftime('%Y-%m-%d %H:%M', time.localtime(record['timestamp']))
                st.caption(f"建立時間: {timestamp} | 模板: {record.get('template', '自訂')}")

            with col2:
                if st.button("👁️ 預覽", key=f"preview_{i}", use_container_width=True):
                    st.session_state.preview_history_item = record
                    st.rerun()

            with col3:
                if st.button("📥 下載", key=f"download_{i}", use_container_width=True):
                    # 觸發下載
                    st.session_state.trigger_download = True
                    st.session_state.final_handout_title = record['title']
                    st.session_state.preview_editor = record['content']
                    st.rerun()

    # 預覽模式
    if 'preview_history_item' in st.session_state:
        record = st.session_state.preview_history_item

        st.divider()
        st.subheader(f"📄 預覽: {record['title']}")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.text_area("內容", record['content'], height=400, disabled=True)
        with col2:
            if st.button("❌ 關閉預覽", use_container_width=True):
                del st.session_state.preview_history_item
                st.rerun()

            if st.button("📝 編輯此講義", use_container_width=True):
                st.session_state.manual_input_content = record['content']
                st.session_state.final_handout_title = record['title']
                st.session_state.preview_editor = record['content']
                st.session_state.app_mode = "📄 講義排版"
                del st.session_state.preview_history_item
                st.rerun()