"""AI 질문 진행 상태.
"""

import streamlit as st

from user.state import context as ctx
from user.state.session import go


def open_quiz():
    st.session_state.quiz = {"step": 0, "answers": {}}
    go("ai_quiz")


def quiz_answer(qid, value):
    q = st.session_state.quiz
    q["answers"][qid] = value
    q["step"] = min(q["step"] + 1, len(ctx.QUESTIONS))  # 선택하면 바로 다음 질문으로


def quiz_back():
    q = st.session_state.quiz
    q["step"] = max(q["step"] - 1, 0)


def quiz_goto(step):
    st.session_state.quiz["step"] = step


def quiz_restart():
    st.session_state.quiz = {"step": 0, "answers": {}}
