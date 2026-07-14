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

    st.divider()
    st.markdown("### " + ("新規教材の登録" if lang == "ja" else "Register a new material"))
    st.caption(
        "CSV形式: rank,greek,meaning,hint"
        if lang == "ja"
        else "CSV format: rank,greek,meaning,hint"
    )

    new_material_title = st.text_input(
        "教材名" if lang == "ja" else "Material title",
        key="new_material_title",
    )
    new_material_category = st.selectbox(
        "分類" if lang == "ja" else "Category",
        ["vocab", "aorist", "participle", "other"],
        key="new_material_category",
    )
    new_material_csv = st.file_uploader(
        "CSV",
        type=["csv"],
        key="new_material_csv",
    )

    if new_material_csv is not None:
        try:
            preview_rows = database.read_material_csv_rows(new_material_csv)
            st.success(f"{len(preview_rows)} cards")
            import pandas as pd

            st.dataframe(
                pd.DataFrame(preview_rows).head(20),
                use_container_width=True,
                hide_index=True,
            )

            can_register = bool(new_material_title.strip()) and len(preview_rows) > 0
            if not new_material_title.strip():
                st.warning(
                    "教材名を入力してください。"
                    if lang == "ja"
                    else "Please enter a material title."
                )

            if st.button(
                "この教材を登録する" if lang == "ja" else "Register this material",
                type="primary",
                disabled=not can_register,
                use_container_width=True,
                key="register_new_material",
            ):
                new_material_id = database.create_material_set(
                    title=new_material_title.strip(),
                    category=new_material_category,
                    description="",
                )
                database.import_material_items(
                    new_material_id, preview_rows, replace=False
                )
                st.success(
                    f"「{new_material_title.strip()}」を登録しました。"
                    if lang == "ja"
                    else f'Registered "{new_material_title.strip()}".'
                )
                st.rerun()
        except Exception as exc:
            st.error(str(exc))
