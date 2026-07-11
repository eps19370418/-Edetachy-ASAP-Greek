from pathlib import Path
import streamlit as st

from modules.common import render_card_trainer


def render(db_path: Path, user_id: int, lang: str) -> None:
    st.subheader("アオリスト" if lang == "ja" else "Aorist")

    def front(card: dict) -> None:
        instruction = (
            "アオリストを答えてください"
            if lang == "ja"
            else "Give the aorist."
        )
        st.markdown(
            f"<div style='text-align:center;font-size:2.25rem;font-weight:700;padding:.8rem'>{card['present']}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='text-align:center;font-size:1.05rem;opacity:.82'>{instruction}</div>",
            unsafe_allow_html=True,
        )

    def answer(card: dict) -> None:
        st.markdown(
            f"<div style='text-align:center;font-size:1.9rem;font-weight:700'>{card['aorist']}</div>",
            unsafe_allow_html=True,
        )
        if card.get("meaning"):
            st.caption(card["meaning"])

    render_card_trainer(db_path, user_id, "aorist", lang, front, answer)
