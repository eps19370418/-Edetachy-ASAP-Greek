from pathlib import Path
import streamlit as st

from modules.common import render_card_trainer


def render(db_path: Path, user_id: int, lang: str) -> None:
    st.subheader("分詞" if lang == "ja" else "Participles")

    def front(card: dict) -> None:
        instruction = (
            "現在分詞とアオリスト分詞を確認してください"
            if lang == "ja"
            else "Recall the present and aorist participles."
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
        present_label = "現在分詞" if lang == "ja" else "Present"
        aorist_label = "アオリスト分詞" if lang == "ja" else "Aorist"
        st.markdown(
            f"""
            <div style='text-align:center'>
              <div style='font-size:.95rem;opacity:.75'>{present_label}</div>
              <div style='font-size:1.65rem;font-weight:700'>{card['present_participle']}</div>
              <br>
              <div style='font-size:.95rem;opacity:.75'>{aorist_label}</div>
              <div style='font-size:1.65rem;font-weight:700'>{card['aorist_participle']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if card.get("meaning"):
            st.caption(card["meaning"])

    render_card_trainer(db_path, user_id, "participle", lang, front, answer)
