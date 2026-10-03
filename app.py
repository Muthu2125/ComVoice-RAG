import os
import streamlit as st
from dotenv import load_dotenv
from comvoice.ingest import extract_document
from comvoice.rag import ComVoiceRAG

load_dotenv()

st.set_page_config(page_title="ComVoice", page_icon="🗣️", layout="wide")
st.title("🗣️ ComVoice")
st.caption("Verified, evidence-first RAG for legal and council documents")

if not os.getenv("GROQ_API_KEY"):
    st.error("Missing GROQ_API_KEY. Copy .env.example to .env and add your Groq key.")
    st.stop()

uploaded = st.file_uploader("Upload a PDF, DOCX or TXT", type=["pdf", "docx", "txt"])

if "rag" not in st.session_state:
    st.session_state.rag = None

if uploaded:
    file_bytes = uploaded.getvalue()
    cache_key = f"{uploaded.name}:{len(file_bytes)}"
    if st.session_state.get("cache_key") != cache_key:
        with st.spinner("Reading and indexing document..."):
            pages = extract_document(uploaded.name, file_bytes)
            rag = ComVoiceRAG(pages)
            rag.build()
            st.session_state.rag = rag
            st.session_state.cache_key = cache_key
            st.session_state.chat = []
        st.success(f"Indexed {len(pages)} page/section records from {uploaded.name}")

rag = st.session_state.rag
if rag:
    left, right = st.columns([1.15, 0.85])

    with left:
        question = st.chat_input("Ask the document anything...")
        for item in st.session_state.get("chat", []):
            with st.chat_message("user"):
                st.write(item["q"])
            with st.chat_message("assistant"):
                st.write(item["a"])

        if question:
            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):
                with st.spinner("Retrieving and verifying evidence..."):
                    result = rag.answer(question)
                st.write(result["answer"])

                if result.get("verified"):
                    st.success("Verified against document evidence")
                else:
                    st.warning("Answer was not fully verifiable; ComVoice abstained.")

                for i, ev in enumerate(result.get("evidence", []), 1):
                    with st.expander(f"Evidence {i} — page {ev['page']}"):
                        st.write(ev["quote"])
                        st.caption(
                            f"Exact quote: {'✓' if ev['quote_verified'] else '✗'} | "
                            f"Numbers: {'✓' if ev['numbers_verified'] else '✗'} | "
                            f"Independent verifier: {'✓' if ev['support_verified'] else '✗'}"
                        )

            st.session_state.setdefault("chat", []).append(
                {"q": question, "a": result["answer"]}
            )

    with right:
        st.subheader("Trust design")
        st.markdown("""
        **Every displayed factual answer must pass:**
        - exact quote verification
        - page verification
        - number/date verification
        - independent support check

        If verification fails, ComVoice returns an abstention instead of guessing.
        """)

        st.subheader("Suggested questions")
        st.markdown("""
        - What is this document about?
        - What obligations does the developer have?
        - What does this mean for residents?
        - What payments or contributions are required?
        - What important dates are mentioned?
        - When does the agreement start or end?
        """)
