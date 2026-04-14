"""
Streamlit Frontend for Invoice Extraction + RAG Q&A.

Tabs:
    1. Extract Invoice — upload a file, call the API, display results
    2. Ask a Question  — ask questions via the RAG pipeline (with conversation memory)
    3. RAG Dashboard   — index stats, re-index, evaluate

Launch:  streamlit run frontend/app.py
"""

import os

import pandas as pd
import requests
import streamlit as st

# Import UI helper components
from frontend.ui_helpers import (
    render_document_viewer,
    render_header_fields,
    render_line_items_table,
    render_financial_waterfall,
    render_processing_timeline,
    render_export_buttons,
    render_query_suggestions,
    render_confidence_indicator,
    render_source_previews,
)

API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── Page config ────────────────────────────────────────────────────────────
# FIXED: Bug P0-2 — Remove emojis for professional appearance
st.set_page_config(
    page_title="Invoice Extraction System",
    page_icon=None,  # No icon for professional appearance
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ─────────────────────────────────────────────────
if "extraction_result" not in st.session_state:
    st.session_state.extraction_result = None
if "uploaded_file_bytes" not in st.session_state:
    st.session_state.uploaded_file_bytes = None
if "uploaded_file_info" not in st.session_state:
    st.session_state.uploaded_file_info = None
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []
if "question_input" not in st.session_state:
    st.session_state.question_input = ""


# ── Sidebar ────────────────────────────────────────────────────────────────
# FIXED: Bug P0-2 — Removed emojis, using clean text
with st.sidebar:
    st.title("Invoice Extraction System")
    st.markdown("---")
    st.subheader("System Status")
    try:
        resp = requests.get(f"{API_URL}/health", timeout=3)
        health = resp.json()
        st.success(f"API Online (v{health.get('version', '?')})")
    except Exception:
        st.error("API Offline")

    # RAG index stats
    try:
        resp = requests.get(f"{API_URL}/rag/stats", timeout=5)
        if resp.status_code == 200:
            stats = resp.json()
            chroma = stats.get("chroma", {})
            bm25 = stats.get("bm25", {})
            st.markdown(f"- ChromaDB: {chroma.get('total_chunks', '?')} chunks")
            st.markdown(f"- BM25: {bm25.get('documents', '?')} documents")
    except Exception:
        pass

    st.markdown("---")
    st.markdown(
        "**Built with:** Tesseract, Ollama, ChromaDB, "
        "Sentence-Transformers, FastAPI, Streamlit"
    )
    st.markdown("---")
    st.caption("RAG: BM25 + SQL + Vector + Hybrid")
    st.caption("Re-ranking: Cross-encoder + RRF")
    st.caption("Query expansion: HyDE")


# ═══════════════════════════════════════════════════════════════════════════
#  Tabs
# ═══════════════════════════════════════════════════════════════════════════
# FIXED: Bug P0-2 — Clean tab labels without emojis
tab1, tab2, tab3 = st.tabs(["Extract Invoice", "Ask Questions", "Dashboard"])


# ═══════════════════════════════════════════════════════════════════════════
#  Tab 1: Extract Invoice
# ═══════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Extract Invoice")
    st.markdown("Upload a single invoice file (PDF, JPG, PNG, TIFF) to extract structured data.")

    uploaded_file = st.file_uploader(
        "Choose an invoice file",
        type=["pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp"],
        accept_multiple_files=False,
        key="invoice_upload",
    )

    # FIXED: Bug P0-2 — Clean button without emoji
    if uploaded_file and st.button("Extract", type="primary"):
        with st.spinner(f"Extracting {uploaded_file.name}..."):
            try:
                # Store file bytes for document viewer
                file_bytes = uploaded_file.getvalue()
                st.session_state.uploaded_file_bytes = file_bytes
                st.session_state.uploaded_file_info = {
                    "name": uploaded_file.name,
                    "type": uploaded_file.name.split('.')[-1] if '.' in uploaded_file.name else 'unknown'
                }

                resp = requests.post(
                    f"{API_URL}/extract",
                    files={"file": (uploaded_file.name, file_bytes)},
                    timeout=300,
                )
                if resp.status_code == 200:
                    try:
                        body = resp.json()
                        st.session_state.extraction_result = body.get("data", body)
                    except ValueError:
                        st.error("Invalid JSON response from API")
                        st.session_state.extraction_result = None
                else:
                    # FIXED: Bug APP-1 — Handle JSON parse errors
                    try:
                        body = resp.json()
                        st.error(f"**API Error ({resp.status_code}):** {body.get('message', body.get('error', body.get('detail', resp.text)))}")
                    except ValueError:
                        st.error(f"**API Error ({resp.status_code}):** {resp.text}")
                    st.session_state.extraction_result = None
            except requests.ConnectionError:
                st.error("Cannot connect to the API. Is uvicorn running?")
                st.session_state.extraction_result = None
            except Exception as e:
                st.error(f"**Error:** {e}")
                st.session_state.extraction_result = None

    # ── Display extraction result in 2-column layout ──────────────────────
    result = st.session_state.extraction_result
    if result:
        st.markdown("---")

        # 2-column layout: Document viewer (left) + Results (right)
        col_doc, col_results = st.columns([1, 1])

        # ── Left Column: Document Viewer ──────────────────────────────────
        with col_doc:
            st.subheader("Original Document")
            # FIXED: Bug APP-2 — Check for required keys before accessing
            file_info = st.session_state.uploaded_file_info
            if st.session_state.uploaded_file_bytes and file_info and file_info.get("name") and file_info.get("type"):
                render_document_viewer(
                    st.session_state.uploaded_file_bytes,
                    file_info["name"],
                    file_info["type"]
                )
            else:
                st.info("Document not available for preview")

        # ── Right Column: Extraction Results ──────────────────────────────
        with col_results:
            st.subheader("Extraction Results")

            st.markdown("---")

            # Processing timeline
            meta = result.get("metadata", {})
            render_processing_timeline(meta)

        # ── Full-width sections below ──────────────────────────────────────
        st.markdown("---")

        # Header fields in card layout
        render_header_fields(result)

        st.markdown("---")

        # Line items table with currency formatting
        line_items = result.get("line_items", [])
        st.subheader(f"Line Items ({len(line_items)})")
        render_line_items_table(line_items)

        st.markdown("---")

        # Financial waterfall chart
        st.subheader("Financial Breakdown")
        render_financial_waterfall(result)

        st.markdown("---")

        # Export buttons
        st.subheader("Export Results")
        render_export_buttons(result)

        st.markdown("---")

        # Raw JSON (collapsed)
        with st.expander("Raw JSON"):
            st.json(result)


# ═══════════════════════════════════════════════════════════════════════════
#  Tab 2: Ask a Question
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Ask a Question")
    st.markdown(
        "Ask natural-language questions about your invoices. "
        "The system supports follow-up questions using conversation memory."
    )

    # ── Strategy legend ────────────────────────────────────────────────
    with st.expander("How it works", expanded=False):
        st.markdown("""
        **Retrieval strategies** (auto-selected based on your question):
        - **SQL** — for aggregation queries ("how many", "total", "average")
        - **BM25** — for keyword/exact lookup (invoice numbers, vendor names, GSTINs)
        - **Vector** — for semantic/vague questions ("similar to", "describe")
        - **Hybrid** — combines BM25 + Vector with Reciprocal Rank Fusion

        **Enhancements:**
        - HyDE query expansion for better vector search
        - Cross-encoder re-ranking for precision
        - Conversation memory for follow-up questions
        """)

    # ── Query suggestions ──────────────────────────────────────────────
    selected_suggestion = render_query_suggestions()
    if selected_suggestion:
        st.session_state.question_input = selected_suggestion
        st.rerun()

    # ── Controls row ──────────────────────────────────────────────────
    col_q, col_clear, col_save = st.columns([4, 1, 1])
    with col_q:
        question = st.text_input(
            "Your question:",
            placeholder="e.g., What is the total amount of all invoices?",
            key="qa_question_input",
            value=st.session_state.get("question_input", ""),
        )
        # Reset the suggestion after it's been used
        if st.session_state.get("question_input") and question:
            st.session_state.question_input = ""

    with col_clear:
        st.markdown("<br>", unsafe_allow_html=True)
        # FIXED: Bug P0-2 — Clean button
        if st.button("Clear Chat"):
            st.session_state.qa_history = []
            try:
                requests.post(f"{API_URL}/ask/clear", timeout=5)
            except Exception:
                pass
            st.rerun()

    with col_save:
        st.markdown("<br>", unsafe_allow_html=True)
        # FIXED: Bug P0-2 — Clean button
        if st.button("Save", help="Save conversation history"):
            import json
            conversation_json = json.dumps(st.session_state.get("qa_history", []), indent=2, ensure_ascii=False)
            st.download_button(
                "Download",
                data=conversation_json,
                file_name="rag_conversation.json",
                mime="application/json",
                key="save_conversation"
            )

    # FIXED: Bug P0-2 — Clean button
    if st.button("Ask", type="primary", disabled=not question):
        with st.spinner("Searching and generating answer..."):
            try:
                resp = requests.post(
                    f"{API_URL}/ask",
                    json={"question": question},
                    timeout=120,
                )
                if resp.status_code == 200:
                    data = resp.json()

                    # Add to history
                    st.session_state.qa_history.append({
                        "question": question,
                        "answer": data.get("answer", ""),
                        "strategy": data.get("strategy", "unknown"),
                        "reasoning": data.get("reasoning", ""),
                        "sources": data.get("sources", []),
                        "reranked": data.get("reranked", False),
                        "context_used": data.get("context_used", ""),
                    })
                    st.rerun()  # Rerun to clear input and display new message
                else:
                    body = resp.json()
                    st.error(f"**API Error ({resp.status_code}):** {body.get('error', body.get('detail', resp.text))}")
            except requests.ConnectionError:
                st.error("Cannot connect to the API. Is uvicorn running?")
            except Exception as e:
                st.error(f"**Error:** {e}")

    # ── Chat-style display ─────────────────────────────────────────────
    if st.session_state.qa_history:
        st.markdown("---")
        for idx, entry in enumerate(st.session_state.qa_history):
            # User message
            st.markdown(f"**You:** {entry['question']}")

            # Assistant message
            st.markdown(f"**Assistant:** {entry['answer']}")

            # Confidence indicator
            render_confidence_indicator(entry)

            # Sources with expandable preview
            sources = entry.get("sources", [])
            if sources:
                with st.expander(f"Sources ({len(sources)})"):
                    for source in sources[:5]:  # Limit to top 5
                        st.markdown(f"- {source}")

            # Context expandable (for debugging/transparency)
            if entry.get("context_used"):
                with st.expander("Context used (detailed)"):
                    st.code(entry["context_used"], language=None)

            st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════
#  Tab 3: RAG Dashboard
# ═══════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("RAG Dashboard")

    # ── Index Stats ──────────────────────────────────────────────────────
    st.subheader("Index Statistics")
    try:
        resp = requests.get(f"{API_URL}/rag/stats", timeout=5)
        if resp.status_code == 200:
            # FIXED: Bug APP-3 — Validate stats is dict before accessing
            try:
                stats = resp.json()
                if not isinstance(stats, dict):
                    stats = {}
            except ValueError:
                stats = {}
            col1, col2, col3, col4 = st.columns(4)
            chroma = stats.get("chroma", {}) if stats else {}
            bm25 = stats.get("bm25", {}) if stats else {}
            with col1:
                st.metric("ChromaDB Chunks", chroma.get("total_chunks", "?"))
            with col2:
                st.metric("BM25 Documents", bm25.get("documents", "?"))
            with col3:
                st.metric("Embedding Model", chroma.get("embedding_model", "?"))
            with col4:
                st.metric("Collection", chroma.get("collection_name", "?"))
    except Exception:
        st.warning("Could not load RAG stats. Is the API running?")

    # ── Re-index ─────────────────────────────────────────────────────────
    st.subheader("Re-index")
    st.markdown("Rebuild ChromaDB and BM25 indexes from all extracted invoices.")
    # FIXED: Bug P0-2 — Clean button
    if st.button("Rebuild Indexes"):
        with st.spinner("Rebuilding indexes..."):
            try:
                resp = requests.post(f"{API_URL}/rag/index", timeout=300)
                if resp.status_code == 200:
                    data = resp.json()
                    st.success(
                        f"Indexes rebuilt. "
                        f"ChromaDB: {data.get('chroma', {}).get('indexed', '?')} new, "
                        f"{data.get('chroma', {}).get('skipped', '?')} skipped. "
                        f"BM25: {data.get('bm25_documents', '?')} documents."
                    )
                else:
                    st.error(f"Failed: {resp.text}")
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Evaluation ───────────────────────────────────────────────────────
    st.subheader("Evaluation")
    st.markdown("Run the RAG evaluation test suite (15 questions, measures routing + retrieval + answer quality).")
    # FIXED: Bug P0-2 — Clean button
    if st.button("Run Evaluation"):
        with st.spinner("Running evaluation (this may take a few minutes)..."):
            try:
                resp = requests.post(f"{API_URL}/rag/evaluate", timeout=600)
                if resp.status_code == 200:
                    report = resp.json()
                    summary = report.get("summary", {})

                    # Summary metrics
                    m1, m2, m3, m4, m5 = st.columns(5)
                    with m1:
                        st.metric("Strategy Accuracy", f"{summary.get('strategy_accuracy', 0):.0%}")
                    with m2:
                        st.metric("Hit@5", f"{summary.get('hit_at_5', 0):.0%}")
                    with m3:
                        st.metric("Mean MRR", f"{summary.get('mean_mrr', 0):.3f}")
                    with m4:
                        st.metric("Answer Quality", f"{summary.get('answer_quality', 0):.0%}")
                    with m5:
                        st.metric("Avg Time", f"{summary.get('avg_time_seconds', 0):.1f}s")

                    # Category breakdown
                    breakdown = report.get("category_breakdown", {})
                    if breakdown:
                        st.markdown("**Per-category breakdown:**")
                        cat_rows = []
                        for cat, s in breakdown.items():
                            cat_rows.append({
                                "Category": cat,
                                "Count": s.get("count", 0),
                                "Strategy Acc.": f"{s.get('strategy_accuracy', 0):.0%}",
                                "Answer Quality": f"{s.get('answer_quality', 0):.0%}",
                            })
                        st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)

                    # Details
                    details = report.get("details", [])
                    if details:
                        with st.expander("Per-question details"):
                            for d in details:
                                scores = d.get("scores", {})
                                # FIXED: Bug P0-2 — Use checkmark symbols instead of emojis
                                strategy_match = '✓' if scores.get('strategy_match') == 1.0 else '✗'
                                hit_at_5 = '✓' if scores.get('hit_at_5') == 1.0 else '✗'
                                st.markdown(
                                    f"**{d['question']}**\n"
                                    f"- Strategy: {d['strategy_used']} | "
                                    f"Match: {strategy_match} | "
                                    f"Hit@5: {hit_at_5} | "
                                    f"Answer: {scores.get('answer_contains', 0):.0%} | "
                                    f"Time: {scores.get('time_seconds', 0):.1f}s"
                                )
                else:
                    st.error(f"Failed: {resp.text}")
            except Exception as e:
                st.error(f"Error: {e}")
