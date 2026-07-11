from pathlib import Path
import os
import streamlit as st

from modules import database


def is_logged_in() -> bool:
    return "user" in st.session_state and st.session_state.user is not None


def logout() -> None:
    keys = [key for key in st.session_state.keys()]
    for key in keys:
        del st.session_state[key]
    st.rerun()


def render_auth(db_path: Path, assets_dir: Path) -> None:
    if "language" not in st.session_state:
        st.session_state.language = "ja"

    lang_choice = st.selectbox(
        "Language / 表示言語",
        ["日本語", "English"],
        index=0 if st.session_state.language == "ja" else 1,
        key="auth_language",
    )
    st.session_state.language = "ja" if lang_choice == "日本語" else "en"
    lang = st.session_state.language

    labels = {
        "ja": {
            "login": "ログイン",
            "register": "ユーザー登録",
            "name": "表示名",
            "pin": "4桁PIN",
            "role": "役割",
            "student": "学習者",
            "teacher": "教師",
            "admin": "管理者",
            "teacher_code": "教師登録コード",
            "admin_code": "管理者登録コード",
            "login_button": "ログイン",
            "register_button": "登録",
            "invalid": "表示名またはPINが違います。",
            "created": "登録しました。ログインしてください。",
            "subtitle": "完璧になる前に、今すぐ原典へ。",
        },
        "en": {
            "login": "Log in",
            "register": "Register",
            "name": "Display name",
            "pin": "4-digit PIN",
            "role": "Role",
            "student": "Student",
            "teacher": "Teacher",
            "admin": "Administrator",
            "teacher_code": "Teacher registration code",
            "admin_code": "Administrator registration code",
            "login_button": "Log in",
            "register_button": "Register",
            "invalid": "Incorrect name or PIN.",
            "created": "Registered. Please log in.",
            "subtitle": "Do not wait for mastery. Get to the text now.",
        },
    }[lang]

    st.image(str(assets_dir / "edetachy_logo.png"), use_container_width=True)
    st.markdown(
        f"<p style='text-align:center;font-size:1.05rem'>{labels['subtitle']}</p>",
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs([labels["login"], labels["register"]])

    with login_tab:
        with st.form("login_form"):
            name = st.text_input(labels["name"])
            pin = st.text_input(labels["pin"], type="password", max_chars=4)
            submitted = st.form_submit_button(labels["login_button"], use_container_width=True)
        if submitted:
            user = database.authenticate(db_path, name, pin)
            if user:
                st.session_state.user = user
                st.rerun()
            st.error(labels["invalid"])

    with register_tab:
        with st.form("register_form"):
            name = st.text_input(labels["name"], key="register_name")
            pin = st.text_input(
                labels["pin"], type="password", max_chars=4, key="register_pin"
            )
            role_label = st.radio(
                labels["role"],
                [labels["student"], labels["teacher"], labels["admin"]],
                horizontal=True,
            )
            registration_code = ""
            if role_label == labels["teacher"]:
                registration_code = st.text_input(labels["teacher_code"], type="password")
            elif role_label == labels["admin"]:
                registration_code = st.text_input(labels["admin_code"], type="password")
            submitted = st.form_submit_button(
                labels["register_button"], use_container_width=True
            )

        if submitted:
            if role_label == labels["teacher"]:
                role = "teacher"
                expected_code = os.getenv("EDETACHY_TEACHER_CODE", "edetachy")
            elif role_label == labels["admin"]:
                role = "admin"
                expected_code = os.getenv("EDETACHY_ADMIN_CODE", "edetachy-admin")
            else:
                role = "student"
                expected_code = ""

            if role in {"teacher", "admin"} and registration_code != expected_code:
                st.error(
                    "登録コードが違います。" if lang == "ja" else "Registration code is incorrect."
                )
            else:
                ok, message = database.create_user(db_path, name, pin, role)
                if ok:
                    st.success(labels["created"])
                else:
                    st.error(message)
