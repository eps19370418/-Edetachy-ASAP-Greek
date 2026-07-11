from pathlib import Path
import streamlit as st

from modules import database


def render(db_path: Path, current_user: dict, lang: str) -> None:
    st.subheader("管理者モード" if lang == "ja" else "Administrator")

    users = database.list_users(db_path)
    deletable = [u for u in users if u["id"] != current_user["id"]]

    if not deletable:
        st.info(
            "削除できる他のユーザーはいません。"
            if lang == "ja"
            else "There are no other users to delete."
        )
        return

    role_labels = {
        "student": "学習者" if lang == "ja" else "Student",
        "teacher": "教師" if lang == "ja" else "Teacher",
        "admin": "管理者" if lang == "ja" else "Administrator",
    }

    st.caption(
        "ユーザーを削除すると、その人の全学習履歴も削除されます。"
        if lang == "ja"
        else "Deleting a user also deletes all of that user's progress."
    )

    option_labels = {
        f"{u['name']}（{role_labels.get(u['role'], u['role'])}）": u for u in deletable
    }
    selected_label = st.selectbox(
        "削除するユーザー" if lang == "ja" else "User to delete",
        list(option_labels.keys()),
    )
    selected = option_labels[selected_label]

    confirmation = st.text_input(
        f"確認のため「{selected['name']}」と入力"
        if lang == "ja"
        else f'Type "{selected["name"]}" to confirm',
        key="admin_delete_confirmation",
    )

    if st.button(
        "ユーザーを削除" if lang == "ja" else "Delete user",
        type="primary",
        disabled=confirmation != selected["name"],
        use_container_width=True,
    ):
        if database.delete_user(db_path, selected["id"]):
            st.success("削除しました。" if lang == "ja" else "Deleted.")
            st.rerun()
        else:
            st.error("削除できませんでした。" if lang == "ja" else "Could not delete the user.")
