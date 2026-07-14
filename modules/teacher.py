from pathlib import Path
import pandas as pd
import streamlit as st

from modules import database


CATEGORY_LABELS = {
    "ja": {"vocab": "単語", "aorist": "アオリスト", "participle": "分詞"},
    "en": {"vocab": "Vocabulary", "aorist": "Aorist", "participle": "Participles"},
}

STATUS_LABELS = {
    "ja": {"known": "覚えた", "familiar": "見たことがある", "unknown": "わからない"},
    "en": {"known": "Known", "familiar": "Looks familiar", "unknown": "Unknown"},
}



def _format_card_line(category: str, row: dict, include_meaning: bool) -> str:
    if category == "vocab":
        main = row["greek"]
        details = row.get("meaning", "")
        hint = row.get("hint", "")
        if include_meaning:
            parts = [main, details]
            if hint:
                parts.append(f"ヒント: {hint}")
            return " — ".join(part for part in parts if part)
        return main

    if category == "aorist":
        main = f'{row["present"]} → {row["aorist"]}'
        return f'{main} — {row.get("meaning", "")}' if include_meaning else main

    main = (
        f'{row["present"]} → '
        f'{row["present_participle"]} / {row["aorist_participle"]}'
    )
    return f'{main} — {row.get("meaning", "")}' if include_meaning else main


def _build_ai_text(
    category: str,
    category_label: str,
    status_label: str,
    target_label: str,
    rows: list[dict],
    include_meaning: bool,
    include_prompt: bool,
    lang: str,
) -> str:
    lines = [_format_card_line(category, row, include_meaning) for row in rows]
    if lang == "ja":
        header = [
            f"【対象】{target_label}",
            f"【カテゴリ】{category_label}",
            f"【ステータス】{status_label}",
            f"【件数】{len(lines)}",
            "",
        ]
        prompt = [
            "以下の語形・語彙を再登場させる古典ギリシア語の練習問題を作成してください。",
            "6問中1問だけ意地悪問題にし、意地悪要素は1つだけにしてください。",
            "日本語訳は直訳寄りにしてください。",
            "",
        ] if include_prompt else []
    else:
        header = [
            f"[Target] {target_label}",
            f"[Category] {category_label}",
            f"[Status] {status_label}",
            f"[Items] {len(lines)}",
            "",
        ]
        prompt = [
            "Create Classical Greek practice exercises that reuse the following vocabulary and forms.",
            "Make exactly one of six questions tricky, with only one tricky element.",
            "Keep the Japanese translations close to the Greek wording.",
            "",
        ] if include_prompt else []

    return "\n".join(prompt + header + lines)


def render(db_path: Path, lang: str) -> None:
    st.subheader("教師モード" if lang == "ja" else "Teacher")

    categories = CATEGORY_LABELS[lang]
    reverse_categories = {v: k for k, v in categories.items()}
    selected_label = st.selectbox(
        "カテゴリ" if lang == "ja" else "Category",
        list(reverse_categories.keys()),
        key="teacher_category",
    )
    category = reverse_categories[selected_label]

    st.markdown("### " + ("学習状況" if lang == "ja" else "Progress"))
    users = database.list_users(db_path)
    students = [u for u in users if u["role"] == "student"]

    summary_rows = []
    for user in students:
        counts = database.progress_counts(db_path, user["id"], category)
        summary_rows.append({"name": user["name"], **counts})
    if summary_rows:
        df = pd.DataFrame(summary_rows).rename(
            columns={
                "name": "名前" if lang == "ja" else "Name",
                "known": "覚えた" if lang == "ja" else "Known",
                "familiar": "見たことがある" if lang == "ja" else "Familiar",
                "unknown": "わからない" if lang == "ja" else "Unknown",
                "unseen": "未学習" if lang == "ja" else "Unseen",
            }
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("学習者がまだ登録されていません。" if lang == "ja" else "No students yet.")

    detail_rows = database.user_progress_rows(db_path, category)
    if detail_rows:
        detail_df = pd.DataFrame(detail_rows)
        pivot = detail_df.pivot_table(
            index=["rank", "card"],
            columns="name",
            values="status",
            aggfunc="last",
        ).reset_index()
        status_labels = STATUS_LABELS[lang]
        for col in pivot.columns[2:]:
            pivot[col] = pivot[col].map(status_labels).fillna("")
        pivot = pivot.rename(
            columns={
                "rank": "順" if lang == "ja" else "Rank",
                "card": "カード" if lang == "ja" else "Card",
            }
        )
        st.dataframe(pivot, use_container_width=True, hide_index=True)



    st.divider()
    st.markdown("### " + ("AI教材用テキスト" if lang == "ja" else "Text for AI exercises"))
    st.caption(
        "学習履歴から語を抽出し、そのままコピーできます。"
        if lang == "ja"
        else "Extract items from progress and copy them directly."
    )

    if not students:
        st.info("学習者がまだ登録されていません。" if lang == "ja" else "No students yet.")
    else:
        target_options = {
            u["name"]: ("user", u["id"])
            for u in students
        }
        target_options[
            "全学習者に共通" if lang == "ja" else "Common to all students"
        ] = ("common", None)

        selected_text_target = st.selectbox(
            "抽出対象" if lang == "ja" else "Target",
            list(target_options.keys()),
            key=f"text_target_{category}",
        )
        target_mode, target_user_id = target_options[selected_text_target]

        text_status_options = {
            STATUS_LABELS[lang]["known"]: "known",
            STATUS_LABELS[lang]["familiar"]: "familiar",
            STATUS_LABELS[lang]["unknown"]: "unknown",
        }
        selected_text_status_label = st.selectbox(
            "ステータス" if lang == "ja" else "Status",
            list(text_status_options.keys()),
            index=1,
            key=f"text_status_{category}",
        )
        selected_text_status = text_status_options[selected_text_status_label]

        col1, col2 = st.columns(2)
        with col1:
            include_meaning = st.checkbox(
                "意味も含める" if lang == "ja" else "Include meanings",
                value=True,
                key=f"text_meaning_{category}",
            )
        with col2:
            include_prompt = st.checkbox(
                "AIへの指示文を付ける" if lang == "ja" else "Include AI prompt",
                value=True,
                key=f"text_prompt_{category}",
            )

        text_rows = database.progress_text_rows(
            db_path,
            category,
            selected_text_status,
            user_id=target_user_id,
            common_to_all_students=(target_mode == "common"),
        )
        output_text = _build_ai_text(
            category,
            selected_label,
            selected_text_status_label,
            selected_text_target,
            text_rows,
            include_meaning,
            include_prompt,
            lang,
        )
        st.text_area(
            "コピーしてAIへ貼り付け" if lang == "ja" else "Copy and paste into AI",
            value=output_text,
            height=320,
            key=f"ai_text_output_{category}_{selected_text_target}_{selected_text_status}",
        )

    st.divider()
    st.markdown("### " + ("CSVを読み込んで上書き" if lang == "ja" else "Replace with CSV"))
    expected = ", ".join(database.EXPECTED_COLUMNS[category])
    st.caption(("必要列: " if lang == "ja" else "Required columns: ") + expected)
    uploaded = st.file_uploader(
        "CSV",
        type=["csv"],
        key=f"upload_{category}",
    )
    if uploaded is not None:
        try:
            rows = database.read_csv_rows(uploaded, category)
            st.success(f"{len(rows)} cards")
            st.dataframe(pd.DataFrame(rows).head(20), use_container_width=True, hide_index=True)
            confirm = st.checkbox(
                "現在のデータと全員の該当履歴を上書きする"
                if lang == "ja"
                else "Replace current cards and reset all progress in this category",
                key=f"confirm_replace_{category}",
            )
            if st.button(
                "上書き実行" if lang == "ja" else "Replace",
                disabled=not confirm,
                use_container_width=True,
                key=f"replace_{category}",
            ):
                database.replace_cards(db_path, category, rows)
                st.success("上書きしました。" if lang == "ja" else "Replaced.")
                st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.divider()
    st.markdown("### " + ("学習履歴リセット" if lang == "ja" else "Reset progress"))
    user_options = {"全員" if lang == "ja" else "Everyone": None}
    user_options.update({u["name"]: u["id"] for u in students})
    selected_user_label = st.selectbox(
        "対象" if lang == "ja" else "User",
        list(user_options.keys()),
        key=f"teacher_reset_user_{category}",
    )
    selected_user = user_options[selected_user_label]

    status_options = {
        "全履歴" if lang == "ja" else "All statuses": None,
        STATUS_LABELS[lang]["known"]: "known",
        STATUS_LABELS[lang]["familiar"]: "familiar",
        STATUS_LABELS[lang]["unknown"]: "unknown",
    }
    selected_status_label = st.selectbox(
        "削除対象" if lang == "ja" else "Status",
        list(status_options.keys()),
        key=f"teacher_reset_status_{category}",
    )
    selected_status = status_options[selected_status_label]

    reset_all_categories = st.checkbox(
        "全カテゴリを対象にする" if lang == "ja" else "Apply to all categories",
        key=f"teacher_reset_all_categories_{category}",
    )
    confirmation = st.text_input(
        "RESET と入力" if lang == "ja" else "Type RESET",
        key="reset_confirmation",
    )
    if st.button(
        "履歴を削除" if lang == "ja" else "Delete progress",
        type="primary",
        disabled=confirmation != "RESET",
        use_container_width=True,
        key=f"teacher_delete_progress_{category}",
    ):
        database.reset_progress(
            db_path,
            user_id=selected_user,
            category=None if reset_all_categories else category,
            status=selected_status,
        )
        st.success("削除しました。" if lang == "ja" else "Deleted.")
        st.rerun()

    st.divider()
    st.markdown("### " + ("教材別 学習状況" if lang == "ja" else "Progress by material"))

    material_sets = database.list_material_sets(active_only=False)
    if not material_sets:
        st.info(
            "登録されている教材はありません。"
            if lang == "ja"
            else "No materials registered yet."
        )
    else:
        material_options = {m["title"]: m["id"] for m in material_sets}
        selected_material_title = st.selectbox(
            "教材" if lang == "ja" else "Material",
            list(material_options.keys()),
            key="teacher_material_select",
        )
        selected_material_id = material_options[selected_material_title]

        items = database.get_material_items(selected_material_id)
        total_items = len(items)

        overview = database.material_teacher_overview(selected_material_id)

        st.caption(
            f"利用者数: {len(overview)}"
            if lang == "ja"
            else f"Participants: {len(overview)}"
        )

        if not overview:
            st.info(
                "この教材の学習履歴はまだありません。"
                if lang == "ja"
                else "No progress recorded for this material yet."
            )
        else:
            material_rows = []
            for row in overview:
                known = row["known"]
                familiar = row["familiar"]
                unknown = row["unknown"]
                unseen = total_items - (known + familiar + unknown)
                material_rows.append(
                    {
                        "name": row["name"],
                        "known": known,
                        "familiar": familiar,
                        "unknown": unknown,
                        "unseen": unseen,
                    }
                )
            material_df = pd.DataFrame(material_rows).rename(
                columns={
                    "name": "参加者名" if lang == "ja" else "Name",
                    "known": "覚えた" if lang == "ja" else "Known",
                    "familiar": "見たことがある" if lang == "ja" else "Familiar",
                    "unknown": "わからない" if lang == "ja" else "Unknown",
                    "unseen": "未学習" if lang == "ja" else "Unseen",
                }
            )
            st.dataframe(material_df, use_container_width=True, hide_index=True)
