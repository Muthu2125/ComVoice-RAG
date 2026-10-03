import os
import streamlit as st
from dotenv import load_dotenv

from comvoice.ingest import extract_document
from comvoice.rag import ComVoiceRAG


# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------
load_dotenv()


# ---------------------------------------------------------
# Streamlit page configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="ComVoice",
    page_icon="assets/comvoice_icon.png",
    layout="wide"
)


# ---------------------------------------------------------
# ComVoice header
# ---------------------------------------------------------
logo_col, title_col = st.columns([1, 8])

with logo_col:
    st.image("assets/comvoice_icon.png", width=85)

with title_col:
    st.markdown("# ComVoice")
    st.caption(
        "Verified AI for community engagement and public education"
    )

st.caption(
    "Evidence-first RAG for legal, planning and council documents"
)

st.divider()


# ---------------------------------------------------------
# Check Groq API key
# ---------------------------------------------------------
if not os.getenv("GROQ_API_KEY"):
    st.error(
        "Missing GROQ_API_KEY. Copy .env.example to .env "
        "and add your Groq API key."
    )
    st.stop()


# ---------------------------------------------------------
# Document upload
# ---------------------------------------------------------
uploaded = st.file_uploader(
    "Upload a PDF, DOCX or TXT",
    type=["pdf", "docx", "txt"]
)


# ---------------------------------------------------------
# Session state
# ---------------------------------------------------------
if "rag" not in st.session_state:
    st.session_state.rag = None

if "chat" not in st.session_state:
    st.session_state.chat = []


# ---------------------------------------------------------
# Read and index uploaded document
# ---------------------------------------------------------
if uploaded:
    file_bytes = uploaded.getvalue()

    cache_key = f"{uploaded.name}:{len(file_bytes)}"

    if st.session_state.get("cache_key") != cache_key:

        with st.spinner("Reading and indexing document..."):
            pages = extract_document(
                uploaded.name,
                file_bytes
            )

            rag = ComVoiceRAG(pages)
            rag.build()

            st.session_state.rag = rag
            st.session_state.cache_key = cache_key
            st.session_state.chat = []

        st.success(
            f"Indexed {len(pages)} page/section records "
            f"from {uploaded.name}"
        )


# ---------------------------------------------------------
# Chatbot
# ---------------------------------------------------------
rag = st.session_state.rag

if rag:

    left, right = st.columns([1.15, 0.85])

    # -----------------------------------------------------
    # Main chatbot
    # -----------------------------------------------------
    with left:

        st.subheader("Ask ComVoice")

        # Show previous conversation
        for item in st.session_state.get("chat", []):

            with st.chat_message("user"):
                st.write(item["q"])

            with st.chat_message("assistant"):
                st.write(item["a"])

        # New user question
        question = st.chat_input(
            "Ask the document anything..."
        )

        if question:

            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):

                with st.spinner(
                    "Retrieving and verifying evidence..."
                ):
                    result = rag.answer(question)

                st.write(result["answer"])

                # -----------------------------------------
                # Verification status
                # -----------------------------------------
                if result.get("verified"):

                    st.success(
                        "✓ Verified against document evidence"
                    )

                else:

                    st.warning(
                        "Answer was not fully verifiable. "
                        "ComVoice abstained rather than guessing."
                    )

                # -----------------------------------------
                # Evidence
                # -----------------------------------------
                for i, ev in enumerate(
                    result.get("evidence", []),
                    1
                ):

                    with st.expander(
                        f"Evidence {i} — Page {ev['page']}"
                    ):

                        st.write(ev["quote"])

                        st.caption(
                            f"Exact quote: "
                            f"{'✓' if ev['quote_verified'] else '✗'}"
                            "  |  "
                            f"Numbers: "
                            f"{'✓' if ev['numbers_verified'] else '✗'}"
                            "  |  "
                            f"Independent verifier: "
                            f"{'✓' if ev['support_verified'] else '✗'}"
                        )

            # Save conversation
            st.session_state.chat.append(
                {
                    "q": question,
                    "a": result["answer"]
                }
            )


    # -----------------------------------------------------
    # Right-side trust panel
    # -----------------------------------------------------
    with right:

        st.subheader("Why trust ComVoice?")

        st.markdown(
            """
            Every factual answer must pass ComVoice's
            evidence checks before it is presented as verified.

            **Verification pipeline**

            - ✓ Relevant document evidence retrieved
            - ✓ Exact quote verified against source text
            - ✓ Page reference checked
            - ✓ Numbers and dates checked
            - ✓ Independent support verification

            If these checks fail, ComVoice does not guess.
            """
        )

        st.divider()

        st.subheader("Suggested questions")

        st.markdown(
            """
            - What is this document about?
            - Why is this agreement needed?
            - What obligations does the developer have?
            - What does this mean for residents?
            - What does this mean for local businesses?
            - What payments or contributions are required?
            - What important dates are mentioned?
            - When does the agreement start or end?
            - What might change because of this document?
            - What happens next?
            """
        )

else:

    st.info(
        "Upload a document above to start asking ComVoice questions."
    )