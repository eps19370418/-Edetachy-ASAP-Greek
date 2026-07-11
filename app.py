from pathlib import Path
import os
import streamlit as st

from modules import auth, database, vocab, aorist, participle, teacher, admin, pdf_export

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "database" / "edetachy.db"

st.set_page_config(
    page_title="Edetachy ASAP, Greek",
    page_icon=str(ASSETS_DIR / "et_icon.png"),
    layout="centered",
)

database.init_db(DB_PATH)
database.seed_if_empty(DB_PATH, DATA_DIR)

if "language" not in st.session_state:
    st.session_state.language = "ja"

TEXT = {
    "ja": {
        "tagline": "Greek, ASAP.",
        "logout": "ログアウト",
        "logged_in": "ログイン中",
        "vocab": "単語",
        "aorist": "アオリスト",
        "participle": "分詞",
        "exports": "PDF出力",
        "teacher": "教師モード",
        "admin": "管理者モード",
        "language": "表示言語",
    },
    "en": {
        "tagline": "Greek, ASAP.",
        "logout": "Log out",
        "logged_in": "Signed in",
        "vocab": "Vocabulary",
        "aorist": "Aorist",
        "participle": "Participles",
        "exports": "PDF exports",
        "teacher": "Teacher",
        "admin": "Administrator",
        "language": "Language",
    },
}

if not auth.is_logged_in():
    auth.render_auth(DB_PATH, ASSETS_DIR)
    st.stop()

lang = st.session_state.language
t = TEXT[lang]
user = st.session_state.user

with st.sidebar:
    st.image(str(ASSETS_DIR / "et_icon.png"), width=105)
    st.caption(f"{t['logged_in']}: **{user['name']}**")
    lang_choice = st.selectbox(
        t["language"],
        ["日本語", "English"],
        index=0 if lang == "ja" else 1,
        key="sidebar_language",
    )
    st.session_state.language = "ja" if lang_choice == "日本語" else "en"
    if st.button(t["logout"], use_container_width=True):
        auth.logout()

st.image(str(ASSETS_DIR / "edetachy_logo.png"), use_container_width=True)
st.markdown(f"<h3 style='text-align:center;margin-top:-0.5rem'>{t['tagline']}</h3>", unsafe_allow_html=True)

tab_names = [t["vocab"], t["aorist"], t["participle"], t["exports"]]
if user["role"] in {"teacher", "admin"}:
    tab_names.append(t["teacher"])
if user["role"] == "admin":
    tab_names.append(t["admin"])

tabs = st.tabs(tab_names)

with tabs[0]:
    vocab.render(DB_PATH, user["id"], lang)

with tabs[1]:
    aorist.render(DB_PATH, user["id"], lang)

with tabs[2]:
    participle.render(DB_PATH, user["id"], lang)

with tabs[3]:
    pdf_export.render(DB_PATH, user["id"], lang)

tab_index = 4
if user["role"] in {"teacher", "admin"}:
    with tabs[tab_index]:
        teacher.render(DB_PATH, lang)
    tab_index += 1

if user["role"] == "admin":
    with tabs[tab_index]:
        admin.render(DB_PATH, user, lang)
