from typing import Any
import streamlit as st

from modules import database
from modules.common import render_material_trainer


TEXT = {
    "ja": {
        "title": "教材",
        "select_label": "教材を選択",
        "no_materials": "現在利用できる教材はありません。",
    },
    "en": {
        "title": "Materials",
        "select_label": "Select a material",
        "no_materials": "No materials are currently available.",
    },
}


def render(user_id: int, lang: str) -> None:
    t = TEXT[lang]
    st.subheader(t["title"])

    material_sets = database.list_material_sets(active_only=True)
    if not material_sets:
        st.info(t["no_materials"])
        return

    options = {m["title"]: m["id"] for m in material_sets}
    selected_title = st.selectbox(
        t["select_label"],
        list(options.keys()),
        key=f"material_select_{user_id}",
    )
    material_set_id = options[selected_title]

    def front(card: dict[str, Any]) -> None:
        st.markdown(
            f"<div style='text-align:center;font-size:2.25rem;font-weight:700;padding:.8rem'>{card['greek']}</div>",
            unsafe_allow_html=True,
        )
        if card.get("hint"):
            st.markdown(
                f"<div style='text-align:center;font-size:1.05rem;opacity:.82'>{card['hint']}</div>",
                unsafe_allow_html=True,
            )

    def answer(card: dict[str, Any]) -> None:
        st.markdown(
            f"<div style='text-align:center;font-size:1.55rem;font-weight:650'>{card['meaning']}</div>",
            unsafe_allow_html=True,
        )

    render_material_trainer(material_set_id, user_id, lang, front, answer)
