from pathlib import Path
from typing import Callable
import streamlit as st

from modules import database

STATUS_TEXT = {
    "ja": {
        "known": "覚えた",
        "familiar": "見たことがある",
        "unknown": "わからない",
        "learn": "通常学習",
        "review": "復習",
        "show": "答えを見る",
        "next_session": "次の20語を始める",
        "restart_review": "復習リストを更新",
        "done": "このセッションは終了です。",
        "no_new": "未学習カードはありません。",
        "no_review": "「見たことがある」カードはありません。",
        "session": "今回",
        "unseen": "未学習",
    },
    "en": {
        "known": "I know it",
        "familiar": "Looks familiar",
        "unknown": "I don't know",
        "learn": "Learn",
        "review": "Review",
        "show": "Show answer",
        "next_session": "Start the next 20",
        "restart_review": "Refresh review list",
        "done": "This session is complete.",
        "no_new": "There are no unseen cards.",
        "no_review": "There are no familiar cards to review.",
        "session": "This session",
        "unseen": "Unseen",
    },
}


def _queue_key(category: str, mode: str, user_id: int) -> str:
    return f"queue_{category}_{mode}_{user_id}"


def _reveal_key(category: str, card_id: int, user_id: int) -> str:
    return f"reveal_{category}_{card_id}_{user_id}"


def reset_queue(category: str, mode: str, user_id: int) -> None:
    st.session_state.pop(_queue_key(category, mode, user_id), None)


def render_card_trainer(
    db_path: Path,
    user_id: int,
    category: str,
    lang: str,
    front_renderer: Callable[[dict], None],
    answer_renderer: Callable[[dict], None],
) -> None:
    t = STATUS_TEXT[lang]
    mode_label = st.radio(
        "学習モード" if lang == "ja" else "Study mode",
        [t["learn"], t["review"]],
        horizontal=True,
        key=f"mode_{category}_{user_id}",
        label_visibility="collapsed",
    )
    mode = "learn" if mode_label == t["learn"] else "review"

    counts = database.progress_counts(db_path, user_id, category)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t["known"], counts["known"])
    c2.metric(t["familiar"], counts["familiar"])
    c3.metric(t["unknown"], counts["unknown"])
    c4.metric(t["unseen"], counts["unseen"])

    key = _queue_key(category, mode, user_id)
    if key not in st.session_state:
        if mode == "learn":
            st.session_state[key] = database.get_unseen_ids(
                db_path, user_id, category, limit=20
            )
        else:
            st.session_state[key] = database.get_ids_by_status(
                db_path, user_id, category, "familiar"
            )

    queue = st.session_state[key]

    if not queue:
        if mode == "learn":
            if counts["unseen"] == 0:
                st.success(t["no_new"])
            else:
                st.success(t["done"])
                if st.button(
                    t["next_session"],
                    use_container_width=True,
                    key=f"new_session_{category}_{user_id}",
                ):
                    reset_queue(category, mode, user_id)
                    st.rerun()
        else:
            st.info(t["no_review"])
            if st.button(
                t["restart_review"],
                use_container_width=True,
                key=f"refresh_review_{category}_{user_id}",
            ):
                reset_queue(category, mode, user_id)
                st.rerun()
        return

    initial_size_key = f"initial_size_{key}"
    if initial_size_key not in st.session_state:
        st.session_state[initial_size_key] = len(queue)
    initial_size = st.session_state[initial_size_key]
    completed = initial_size - len(queue)
    st.progress(completed / max(initial_size, 1), text=f"{t['session']}: {completed}/{initial_size}")

    card_id = queue[0]
    card = database.get_card(db_path, category, card_id)
    if card is None:
        queue.pop(0)
        st.rerun()

    with st.container(border=True):
        front_renderer(card)
        reveal_key = _reveal_key(category, card_id, user_id)
        revealed = st.session_state.get(reveal_key, False)

        if not revealed:
            if st.button(
                t["show"],
                use_container_width=True,
                key=f"show_{category}_{card_id}_{user_id}",
            ):
                st.session_state[reveal_key] = True
                st.rerun()
        else:
            st.divider()
            answer_renderer(card)

            cols = st.columns(3)
            status_buttons = [
                ("known", t["known"]),
                ("familiar", t["familiar"]),
                ("unknown", t["unknown"]),
            ]
            for col, (status, label) in zip(cols, status_buttons):
                if col.button(
                    label,
                    use_container_width=True,
                    key=f"{category}_{card_id}_{status}_{user_id}",
                ):
                    database.save_progress(db_path, user_id, category, card_id, status)
                    queue.pop(0)
                    st.session_state.pop(reveal_key, None)
                    st.rerun()
# ============================================================
# 汎用教材セット用トレーナー（フェーズ1: 新規教材用）
# render_card_trainer と同じロジックを material_* 関数で再現
# ============================================================

MATERIAL_STATUS_TEXT = STATUS_TEXT


def _material_queue_key(material_set_id: int, mode: str, user_id: int) -> str:
    return f"mqueue_{material_set_id}_{mode}_{user_id}"


def _material_reveal_key(material_set_id: int, item_id: int, user_id: int) -> str:
    return f"mreveal_{material_set_id}_{item_id}_{user_id}"


def reset_material_queue(material_set_id: int, mode: str, user_id: int) -> None:
    st.session_state.pop(_material_queue_key(material_set_id, mode, user_id), None)


def render_material_trainer(
    material_set_id: int,
    user_id: int,
    lang: str,
    front_renderer: Callable[[dict], None],
    answer_renderer: Callable[[dict], None],
) -> None:
    t = MATERIAL_STATUS_TEXT[lang]
    mode_label = st.radio(
        "学習モード" if lang == "ja" else "Study mode",
        [t["learn"], t["review"]],
        horizontal=True,
        key=f"mmode_{material_set_id}_{user_id}",
        label_visibility="collapsed",
    )
    mode = "learn" if mode_label == t["learn"] else "review"

    counts = database.material_progress_counts(user_id, material_set_id)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t["known"], counts["known"])
    c2.metric(t["familiar"], counts["familiar"])
    c3.metric(t["unknown"], counts["unknown"])
    c4.metric(t["unseen"], counts["unseen"])

    key = _material_queue_key(material_set_id, mode, user_id)
    if key not in st.session_state:
        if mode == "learn":
            st.session_state[key] = database.get_material_unseen_ids(
                user_id, material_set_id, limit=20
            )
        else:
            st.session_state[key] = database.get_material_ids_by_status(
                user_id, material_set_id, "familiar"
            )

    queue = st.session_state[key]

    if not queue:
        if mode == "learn":
            if counts["unseen"] == 0:
                st.success(t["no_new"])
            else:
                st.success(t["done"])
                if st.button(
                    t["next_session"],
                    use_container_width=True,
                    key=f"mnew_session_{material_set_id}_{user_id}",
                ):
                    reset_material_queue(material_set_id, mode, user_id)
                    st.rerun()
        else:
            st.info(t["no_review"])
            if st.button(
                t["restart_review"],
                use_container_width=True,
                key=f"mrefresh_review_{material_set_id}_{user_id}",
            ):
                reset_material_queue(material_set_id, mode, user_id)
                st.rerun()
        return

    initial_size_key = f"minitial_size_{key}"
    if initial_size_key not in st.session_state:
        st.session_state[initial_size_key] = len(queue)
    initial_size = st.session_state[initial_size_key]
    completed = initial_size - len(queue)
    st.progress(completed / max(initial_size, 1), text=f"{t['session']}: {completed}/{initial_size}")

    item_id = queue[0]
    card = database.get_material_item(item_id)
    if card is None:
        queue.pop(0)
        st.rerun()

    with st.container(border=True):
        front_renderer(card)
        reveal_key = _material_reveal_key(material_set_id, item_id, user_id)
        revealed = st.session_state.get(reveal_key, False)

        if not revealed:
            if st.button(
                t["show"],
                use_container_width=True,
                key=f"mshow_{material_set_id}_{item_id}_{user_id}",
            ):
                st.session_state[reveal_key] = True
                st.rerun()
        else:
            st.divider()
            answer_renderer(card)

            cols = st.columns(3)
            status_buttons = [
                ("known", t["known"]),
                ("familiar", t["familiar"]),
                ("unknown", t["unknown"]),
            ]
            for col, (status, label) in zip(cols, status_buttons):
                if col.button(
                    label,
                    use_container_width=True,
                    key=f"m{material_set_id}_{item_id}_{status}_{user_id}",
                ):
                    database.save_material_progress(
                        user_id, material_set_id, item_id, status
                    )
                    queue.pop(0)
                    st.session_state.pop(reveal_key, None)
                    st.rerun()
