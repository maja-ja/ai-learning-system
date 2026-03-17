import streamlit as st
import os
from pathlib import Path
from utils import inject_custom_css
from pages import (
    page_etymon_home, page_etymon_learn, page_etymon_lab, run_handout_app
)
from exam_db import page_exam_db
from utils import load_db

st.set_page_config(page_title="AI 教育工作站 (Etymon + Handout)", page_icon="🏫", layout="wide")

APP_MODES = [
    "🔬 單字解碼",
    "📚 學測資料庫",
    "📄 講義排版"
]

ETYMON_SUB_MENU = ["🏠 首頁概覽", "📖 學習搜尋", "🔬 解碼實驗室"]

SESSION_DEFAULTS = {
    "app_mode": APP_MODES[0],
    "etymon_page": ETYMON_SUB_MENU[0],
    "exam_db_auth_ok": False,
    "curr_w": None,
    "back_to": None,
    "is_admin": True,
}


@st.cache_data(show_spinner=False)
def load_db_cached():
    return load_db()


def init_session_state():
    for key, default_value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def render_sidebar():
    with st.sidebar:
        st.title("🏫 AI 教育工作站")

        if st.session_state.app_mode not in APP_MODES:
            st.session_state.app_mode = APP_MODES[0]

        selected_mode = st.radio(
            "模組導航",
            APP_MODES,
            index=APP_MODES.index(st.session_state.app_mode),
            key="sidebar_mode"
        )
        st.session_state.app_mode = selected_mode

        st.write("---")

        qr_path = Path(__file__).resolve().parents[1] / "qrcode.png"
        with st.expander("💖 贊助 / LINE Pay", expanded=False):
            if qr_path.exists():
                st.image(str(qr_path), use_container_width=True, caption="LINE Pay QRCode")
            else:
                st.caption("找不到 qrcode.png（請放在專案根目錄）")

        st.write("---")


def render_router():
    if st.session_state.app_mode == "🔬 單字解碼":
        df = load_db_cached()

        selected_sub = st.radio(
            "功能選單",
            ETYMON_SUB_MENU,
            index=ETYMON_SUB_MENU.index(st.session_state.etymon_page)
            if st.session_state.etymon_page in ETYMON_SUB_MENU
            else 0,
            horizontal=True
        )

        if selected_sub != st.session_state.etymon_page:
            st.session_state.etymon_page = selected_sub
            st.rerun()

        if st.session_state.etymon_page == "🏠 首頁概覽":
            page_etymon_home(df)
        elif st.session_state.etymon_page == "📖 學習搜尋":
            page_etymon_learn(df)
        elif st.session_state.etymon_page == "🔬 解碼實驗室":
            page_etymon_lab()

    elif st.session_state.app_mode == "📚 學測資料庫":
        page_exam_db()

    elif st.session_state.app_mode == "📄 講義排版":
        run_handout_app()

def main():
    """
    AI 教育工作站 v5.2 - 無全域登入
    側邊欄 + 只在學測資料庫需要密碼保護 + 模塊化
    """
    inject_custom_css()

    init_session_state()

    render_sidebar()
    render_router()

# 啟動程式
if __name__ == "__main__":
    main()