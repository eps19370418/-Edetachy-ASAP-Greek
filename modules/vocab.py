from pathlib import Path
import streamlit as st

from modules.common import render_card_trainer


def render(db_path: Path, user_id: int, lang: str) -> None:
    title = "単語" if lang == "ja" else "Vocabulary"
    st.subheader(title)

    def front(card: dict) -> None:
        st.markdown(
            f"<div style='text-align:center;font-size:2.25rem;font-weight:700;padding:.8rem'>{card['greek']}</div>",
            unsafe_allow_html=True,
        )
        if card.get("hint"):
            st.markdown(
                f"<div style='text-align:center;font-size:1.05rem;opacity:.82'>{card['hint']}</div>",
                unsafe_allow_html=True,
            )

    def answer(card: dict) -> None:
        st.markdown(
            f"<div style='text-align:center;font-size:1.55rem;font-weight:650'>{card['meaning']}</div>",
            unsafe_allow_html=True,
        )

    render_card_trainer(db_path, user_id, "vocab", lang, front, answer)
