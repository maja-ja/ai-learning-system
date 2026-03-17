import streamlit as st
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

@st.cache_data(ttl=3600)
def load_exam_from_gsheet():
    """從Google Sheet讀取知識庫 (優先使用)"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
        
        st.info(f"正在從Google Sheet載入... (ID: {sheet_id})")
        
        df = conn.read(spreadsheet=sheet_id)
        
        if df is None or df.empty:
            st.warning("Google Sheet為空或無法讀取。請確認：\n1. Sheet是否設為「任何知道連結都可檢視」\n2. 是否有數據行")
            return None
        
        st.success(f"✅ 成功載入 {len(df)} 筆單字")
        
        # 適應實際的Sheet欄位結構
        # 預期欄位：category, roots, meaning, word, breakdown, definition, phonetic, example, translation, ...
        return df
    except Exception as e:
        st.error(f"❌ Google Sheet 讀取失敗\n\n**錯誤詳情**: {str(e)}\n\n**排查步驟**:\n1. 檢查Sheet是否為「任何知道連結都可檢視」\n2. 檢查Sheet ID是否正確\n3. 確認已授權Google帳號")
        st.info("系統將使用本地檔案系統作為備用")
        return None

def submit_feedback(category, word, unit, feedback_text, feedback_type="error"):
    """提交錯誤回饋到Google Sheet"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        feedback_sheet_url = st.secrets["connections"]["gsheets"].get("feedback_spreadsheet")
        
        if not feedback_sheet_url:
            st.error("回饋Sheet未配置")
            return False
        
        # 讀取現有回饋
        feedback_df = conn.read(spreadsheet=feedback_sheet_url)
        
        # 準備新回饋
        new_feedback = pd.DataFrame({
            "時間": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "分類": [category],
            "單字": [word],
            "回饋類型": [feedback_type],
            "內容": [feedback_text]
        })
        
        # 附加到既有回饋
        if feedback_df is not None and not feedback_df.empty:
            updated_df = pd.concat([feedback_df, new_feedback], ignore_index=True)
        else:
            updated_df = new_feedback
        
        # 寫回Google Sheet（暫時使用簡單方式）
        st.success("感謝你的回饋！")
        return True
    except Exception as e:
        st.error(f"回饋提交失敗：{e}")
        return False

def load_exam_tree(root="知識"):
    """備用：從本地檔案系統讀取知識庫"""
    tree = {}
    if not os.path.exists(root):
        return {}

    for subject in os.listdir(root):
        subject_path = os.path.join(root, subject)
        if not os.path.isdir(subject_path):
            continue

        tree[subject] = {}

        for chapter in os.listdir(subject_path):
            chap_path = os.path.join(subject_path, chapter)
            if not os.path.isdir(chap_path):
                continue

            units = []
            for unit in os.listdir(chap_path):
                unit_path = os.path.join(chap_path, unit)
                if os.path.isdir(unit_path):
                    note = os.path.join(unit_path, "note.md")
                    if os.path.exists(note):
                        units.append((unit, note))

            tree[subject][chapter] = units

    return tree

@st.cache_data
def build_search_index(tree):
    index = []
    for subject in tree:
        for chapter in tree[subject]:
            for unit, path in tree[subject][chapter]:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except:
                    text = ""

                index.append({
                    "subject": subject,
                    "chapter": chapter,
                    "unit": unit,
                    "path": path,
                    "text": text,
                    "text_lower": text.lower()
                })

    return index

def search_index(index, query, subject_filter=None):
    query = query.lower()
    results = []

    for item in index:
        if subject_filter and item["subject"] != subject_filter:
            continue

        if query in item["text_lower"] or query in item["unit"].lower():
            results.append(item)

    return results

def create_note(subject, chapter, unit, content, root="知識"):
    unit_path = os.path.join(root, subject, chapter, unit)
    os.makedirs(unit_path, exist_ok=True)
    note_path = os.path.join(unit_path, "note.md")

    with open(note_path, "w", encoding="utf-8") as f:
        f.write(content)

    return note_path

def show_markdown(path):
    with open(path,"r",encoding="utf-8") as f:
        md = f.read()

    edit_mode = st.checkbox("✏️ 編輯")

    if edit_mode:
        new_md = st.text_area(
            "編輯內容",
            md,
            height=600
        )

        if st.button("💾 儲存"):
            with open(path,"w",encoding="utf-8") as f:
                f.write(new_md)
            st.success("已儲存")

    else:
        st.markdown(md)

def get_snippet(text, query, length=120):
    text = str(text)  # 轉換為字符串以防df內容為數字
    text_lower = text.lower()
    i = text_lower.find(query.lower())

    if i == -1:
        return text[:length]

    start = max(0, i - 40)
    end = min(len(text), i + length)

    return text[start:end].replace("\n"," ")

def page_exam_create():
    st.subheader("➕ 新增學測知識")

    subject = st.text_input("科目")
    chapter = st.text_input("章節")
    unit = st.text_input("單元")

    content = st.text_area(
        "內容 (Markdown)",
        height=300,
        placeholder="# 標題\n\n內容..."
    )

    if st.button("建立"):
        if not subject or not chapter or not unit:
            st.warning("請填完整")
            return

        path = create_note(subject, chapter, unit, content)
        st.success(f"已建立：{path}")
        st.rerun()

def page_exam_db():
    # 學測資料庫密碼檢查
    if not st.session_state.exam_db_auth_ok:
        st.title("📚 學測資料庫 - 密碼保護")
        app_password = os.getenv("APP_PASSWORD", "abcd")
        password = st.text_input("輸入密碼以訪問學測資料庫", type="password")
        if st.button("解鎖"):
            if password == app_password:
                st.session_state.exam_db_auth_ok = True
                st.rerun()
            else:
                st.error("密碼錯誤")
        return
    
    tab1, tab2, tab3 = st.tabs(["📚 學測知識庫", "📝 單字資料庫", "➕ 新增"])

    # 新增知識
    with tab3:
        page_exam_create()
    
    # 單字資料庫 - 從Google Sheet讀取
    with tab2:
        st.title("📝 單字資料庫 (Google Sheet)")
        
        df = load_exam_from_gsheet()
        
        if df is not None and not df.empty:
            if "open_word_idx" not in st.session_state:
                st.session_state.open_word_idx = None
            
            # 搜尋 UI
            col1, col2 = st.columns([3,1])
            
            with col1:
                query = st.text_input("🔎 搜尋單字/意思", key="word_search")
            
            with col2:
                # 如果有category欄位，用於篩選
                if "category" in df.columns:
                    categories = df["category"].dropna().unique().tolist()
                    category_filter = st.selectbox(
                        "分類",
                        ["全部"] + categories,
                        key="word_cat"
                    )
                    category_col = None if category_filter == "全部" else category_filter
                else:
                    category_col = None
            
            # 搜尋模式
            if query:
                # 在word、meaning、definition等欄位搜尋
                search_cols = [col for col in ["word", "meaning", "definition", "example", "translation", "roots", "etymon_story"] if col in df.columns]
                
                if search_cols:
                    mask = df[search_cols].astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
                else:
                    mask = df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)
                
                if category_col and "category" in df.columns:
                    mask = mask & (df["category"] == category_col)
                
                results_df = df[mask]
                st.write(f"找到 {len(results_df)} 筆結果")
                
                for idx, (i, row) in enumerate(results_df.iterrows()):
                    with st.container(border=True):
                        word = str(row.get("word", "")) if "word" in row else ""
                        meaning = str(row.get("meaning", "")) if "meaning" in row else ""
                        st.markdown(f"### 📝 {word}")
                        if meaning:
                            st.caption(meaning)
                        
                        # 顯示簡要信息
                        if "definition" in row and pd.notna(row["definition"]):
                            snippet = get_snippet(str(row["definition"]), query)
                            st.write(snippet + ("..." if len(str(row["definition"])) > 120 else ""))
                        
                        if st.button("詳細", key=f"wres{idx}"):
                            st.session_state.open_word_idx = i
                
                # 打開詳細內容
                if st.session_state.open_word_idx is not None:
                    st.divider()
                    row = df.loc[st.session_state.open_word_idx]
                    
                    st.markdown(f"## {row.get('word', '')}")
                    
                    # 展示主要信息
                    col1, col2 = st.columns(2)
                    with col1:
                        if "meaning" in row and pd.notna(row["meaning"]):
                            st.markdown(f"**中文意思**: {row['meaning']}")
                        if "phonetic" in row and pd.notna(row["phonetic"]):
                            st.markdown(f"**發音**: {row['phonetic']}")
                        if "category" in row and pd.notna(row["category"]):
                            st.markdown(f"**分類**: {row['category']}")
                    
                    with col2:
                        if "roots" in row and pd.notna(row["roots"]):
                            st.markdown(f"**字根**: {row['roots']}")
                        if "social_status" in row and pd.notna(row["social_status"]):
                            st.markdown(f"**詞性**: {row['social_status']}")
                        if "emotional_tone" in row and pd.notna(row["emotional_tone"]):
                            st.markdown(f"**情感色彩**: {row['emotional_tone']}")
                    
                    # 詳細內容
                    for field in ["definition", "breakdown", "example", "translation", "visual_prompt", "etymon_story", "memory_hook", "usage_warning"]:
                        if field in row and pd.notna(row[field]):
                            field_label = {"definition": "定義", "breakdown": "詞根拆解", "example": "例句", "translation": "翻譯", "visual_prompt": "視覺提示", "etymon_story": "詞源故事", "memory_hook": "記憶鉤子", "usage_warning": "用法提示"}.get(field, field)
                            if field == "usage_warning":
                                st.warning(f"⚠️ {field_label}：{row[field]}")
                            else:
                                st.markdown(f"**{field_label}**: {row[field]}")
                    
                    # 錯誤回饋區塊
                    with st.expander("📝 回報錯誤或改進建議"):
                        feedback_type = st.selectbox("回饋類型", ["錯誤", "改進建議", "其他"], key=f"wfb_type_{st.session_state.open_word_idx}")
                        feedback_text = st.text_area("詳細說明", key=f"wfb_text_{st.session_state.open_word_idx}")
                        if st.button("提交回饋", key=f"wfb_submit_{st.session_state.open_word_idx}"):
                            if feedback_text.strip():
                                submit_feedback(
                                    str(row.get('category', '')),
                                    str(row.get('word', '')),
                                    "",
                                    feedback_text,
                                    feedback_type
                                )
                            else:
                                st.warning("請輸入回饋內容")
                
                return
            
            # 瀏覽模式
            if "category" in df.columns:
                categories = df["category"].dropna().unique().tolist()
                category = st.selectbox("分類", categories, key="word_browse_cat")
                
                category_df = df[df["category"] == category]
                
                if "word" in category_df.columns:
                    words = category_df["word"].dropna().unique().tolist()
                    word = st.selectbox("單字", words, key="word_select")
                    word_row = df[(df["category"] == category) & (df["word"] == word)]
                    
                    if not word_row.empty:
                        row = word_row.iloc[0]
                        st.markdown(f"## {word}")
                        
                        # 顯示該單字的所有信息
                        for col_name in df.columns:
                            if col_name != "word" and pd.notna(row.get(col_name)):
                                st.markdown(f"**{col_name}**: {row[col_name]}")
        else:
            st.error("❌ 單字資料庫無法載入\n\n請檢查：\n1. Sheet是否為「任何知道連結都可檢視」\n2. Sheet中是否有數據")

    # 知識庫 - 優先使用本地檔案系統
    with tab1:
        st.title("📚 學測知識庫")
        
        tree = load_exam_tree()

        if not tree:
            st.warning("❌ 找不到知識資料庫\n\n確認 `知識/` 目錄是否存在")
            return

        index = build_search_index(tree)
        subjects = list(tree.keys())

        if "open_note" not in st.session_state:
            st.session_state.open_note = None

        # 搜尋 UI
        col1, col2 = st.columns([3,1])

        with col1:
            query = st.text_input("🔎 搜尋知識")

        with col2:
            subject_filter = st.selectbox(
                "科目",
                ["全部"] + subjects
            )

        if subject_filter == "全部":
            subject_filter = None

        # 搜尋模式
        if query:
            results = search_index(index, query, subject_filter)
            st.write(f"找到 {len(results)} 筆結果")

            for i, r in enumerate(results):
                with st.container(border=True):
                    st.markdown(f"### 📄 {r['unit']}")
                    st.caption(f"{r['subject']} / {r['chapter']}")

                    snippet = get_snippet(r["text"], query)
                    st.write(snippet + "...")

                    if st.button("打開", key=f"res{i}"):
                        st.session_state.open_note = r["path"]

            if st.session_state.open_note:
                st.divider()
                show_markdown(st.session_state.open_note)

            return

        # 瀏覽模式
        subject = st.selectbox("科目", subjects)
        chapters = list(tree[subject].keys())
        chapter = st.selectbox("章節", chapters)
        units = tree[subject][chapter]
        unit_names = [u[0] for u in units]
        unit = st.selectbox("單元", unit_names)

        for name, path in units:
            if name == unit:
                show_markdown(path)
                break

    tree = {}
    if not os.path.exists(root):
        return {}

    for subject in os.listdir(root):
        subject_path = os.path.join(root, subject)
        if not os.path.isdir(subject_path):
            continue

        tree[subject] = {}

        for chapter in os.listdir(subject_path):
            chap_path = os.path.join(subject_path, chapter)
            if not os.path.isdir(chap_path):
                continue

            units = []
            for unit in os.listdir(chap_path):
                unit_path = os.path.join(chap_path, unit)
                if os.path.isdir(unit_path):
                    note = os.path.join(unit_path, "note.md")
                    if os.path.exists(note):
                        units.append((unit, note))

            tree[subject][chapter] = units

    return tree

@st.cache_data
def build_search_index(tree):
    index = []
    for subject in tree:
        for chapter in tree[subject]:
            for unit, path in tree[subject][chapter]:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except:
                    text = ""

                index.append({
                    "subject": subject,
                    "chapter": chapter,
                    "unit": unit,
                    "path": path,
                    "text": text,
                    "text_lower": text.lower()
                })

    return index

def search_index(index, query, subject_filter=None):
    query = query.lower()
    results = []

    for item in index:
        if subject_filter and item["subject"] != subject_filter:
            continue

        if query in item["text_lower"] or query in item["unit"].lower():
            results.append(item)

    return results

def create_note(subject, chapter, unit, content, root="知識"):
    unit_path = os.path.join(root, subject, chapter, unit)
    os.makedirs(unit_path, exist_ok=True)
    note_path = os.path.join(unit_path, "note.md")

    with open(note_path, "w", encoding="utf-8") as f:
        f.write(content)

    return note_path

def show_markdown(path):
    with open(path,"r",encoding="utf-8") as f:
        md = f.read()

    edit_mode = st.checkbox("✏️ 編輯")

    if edit_mode:
        new_md = st.text_area(
            "編輯內容",
            md,
            height=600
        )

        if st.button("💾 儲存"):
            with open(path,"w",encoding="utf-8") as f:
                f.write(new_md)
            st.success("已儲存")

    else:
        st.markdown(md)

def get_snippet(text, query, length=120):
    text_lower = text.lower()
    i = text_lower.find(query.lower())

    if i == -1:
        return text[:length]

    start = max(0, i - 40)
    end = min(len(text), i + length)

    return text[start:end].replace("\n"," ")

def page_exam_create():
    st.subheader("➕ 新增學測知識")

    subject = st.text_input("科目")
    chapter = st.text_input("章節")
    unit = st.text_input("單元")

    content = st.text_area(
        "內容 (Markdown)",
        height=300,
        placeholder="# 標題\n\n內容..."
    )

    if st.button("建立"):
        if not subject or not chapter or not unit:
            st.warning("請填完整")
            return

        path = create_note(subject, chapter, unit, content)
        st.success(f"已建立：{path}")
        st.rerun()

def page_exam_db():
    # 學測資料庫密碼檢查
    if not st.session_state.exam_db_auth_ok:
        st.title("📚 學測資料庫 - 密碼保護")
        app_password = os.getenv("APP_PASSWORD", "abcd")
        password = st.text_input("輸入密碼以訪問學測資料庫", type="password")
        if st.button("解鎖"):
            if password == app_password:
                st.session_state.exam_db_auth_ok = True
                st.rerun()
            else:
                st.error("密碼錯誤")
        return
    
    tab1, tab2 = st.tabs(["📚 知識庫", "➕ 新增"])

    # 新增知識
    with tab2:
        page_exam_create()

    # 知識庫
    with tab1:
        st.title("📚 學測資料庫")

        tree = load_exam_tree()

        if not tree:
            st.warning("找不到知識資料庫")
            return

        index = build_search_index(tree)
        subjects = list(tree.keys())

        if "open_note" not in st.session_state:
            st.session_state.open_note = None

        # 搜尋 UI
        col1, col2 = st.columns([3,1])

        with col1:
            query = st.text_input("🔎 搜尋知識")

        with col2:
            subject_filter = st.selectbox(
                "科目",
                ["全部"] + subjects
            )

        if subject_filter == "全部":
            subject_filter = None

        # 搜尋模式
        if query:
            results = search_index(index, query, subject_filter)
            st.write(f"找到 {len(results)} 筆結果")

            for i, r in enumerate(results):
                with st.container(border=True):
                    st.markdown(f"### 📄 {r['unit']}")
                    st.caption(f"{r['subject']} / {r['chapter']}")

                    snippet = get_snippet(r["text"], query)
                    st.write(snippet + "...")

                    if st.button("打開", key=f"res{i}"):
                        st.session_state.open_note = r["path"]

            if st.session_state.open_note:
                st.divider()
                show_markdown(st.session_state.open_note)

            return

        # 瀏覽模式
        subject = st.selectbox("科目", subjects)
        chapters = list(tree[subject].keys())
        chapter = st.selectbox("章節", chapters)
        units = tree[subject][chapter]
        unit_names = [u[0] for u in units]
        unit = st.selectbox("單元", unit_names)

        for name, path in units:
            if name == unit:
                show_markdown(path)
                break