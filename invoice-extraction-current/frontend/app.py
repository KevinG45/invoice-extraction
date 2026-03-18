"""
Streamlit Frontend for Invoice Extraction + RAG Q&A.

Tabs:
    1. Extract Invoice — upload a file, call the API, display results
    2. Ask a Question  — ask questions via the RAG pipeline

Launch:  streamlit run frontend/app.py
"""

import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Invoice Extraction System",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ─────────────────────────────────────────────────
if "extraction_result" not in st.session_state:
    st.session_state.extraction_result = None
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📄 Invoice Extractor")
    st.markdown("---")
    st.subheader("System Status")
    try:
        resp = requests.get(f"{API_URL}/health", timeout=3)
        health = resp.json()
        st.markdown(f"- API: ✅ Online (v{health.get('version', '?')})")
    except Exception:
        st.markdown("- API: ❌ Offline")
    st.markdown("---")
    st.markdown(
        "**Built with:** PaddleOCR, Ollama, ChromaDB, "
        "Sentence-Transformers, FastAPI, Streamlit"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Tabs
# ═══════════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs(["📤 Extract Invoice", "💬 Ask a Question"])


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

    if uploaded_file and st.button("🚀 Extract", type="primary"):
        with st.spinner(f"Extracting {uploaded_file.name}..."):
            try:
                resp = requests.post(
                    f"{API_URL}/extract",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue())},
                    timeout=300,
                )
                if resp.status_code == 200:
                    body = resp.json()
                    st.session_state.extraction_result = body.get("data", body)
                else:
                    body = resp.json()
                    st.error(f"**API Error ({resp.status_code}):** {body.get('error', body.get('detail', resp.text))}")
                    st.session_state.extraction_result = None
            except requests.ConnectionError:
                st.error("Cannot connect to the API. Is uvicorn running?")
                st.session_state.extraction_result = None
            except Exception as e:
                st.error(f"**Error:** {e}")
                st.session_state.extraction_result = None

    # ── Display extraction result ─────────────────────────────────────────
    result = st.session_state.extraction_result
    if result:
        st.markdown("---")
        meta = result.get("metadata", {})
        validation = result.get("validation", {})

        # ── Validation badge ──────────────────────────────────────────────
        if validation.get("passed"):
            st.success("✅ Validation PASSED")
        else:
            st.error("❌ Validation FAILED")
            for w in validation.get("warnings", []):
                st.warning(w)

        # ── Header fields table ───────────────────────────────────────────
        st.subheader("Extracted Header Fields")

        header_fields = [
            ("Invoice Number", result.get("invoice_number")),
            ("Invoice Date", result.get("invoice_date")),
            ("Due Date", result.get("due_date")),
            ("PO Number", result.get("purchase_order_number")),
            ("Vendor Name", (result.get("vendor") or {}).get("name")),
            ("Vendor Tax ID", (result.get("vendor") or {}).get("tax_id")),
            ("Vendor Address", (result.get("vendor") or {}).get("address")),
            ("Vendor Email", (result.get("vendor") or {}).get("email")),
            ("Vendor Phone", (result.get("vendor") or {}).get("phone")),
            ("Bill To Name", (result.get("bill_to") or {}).get("name")),
            ("Bill To Address", (result.get("bill_to") or {}).get("address")),
            ("Subtotal", result.get("subtotal")),
            ("Discount", result.get("discount")),
            ("Tax Rate", result.get("tax_rate")),
            ("Tax Amount", result.get("tax_amount")),
            ("Shipping", result.get("shipping")),
            ("Total Amount", result.get("total_amount")),
            ("Amount Paid", result.get("amount_paid")),
            ("Amount Due", result.get("amount_due")),
            ("Currency", result.get("currency")),
            ("Payment Terms", result.get("payment_terms")),
            ("Payment Method", result.get("payment_method")),
            ("Bank Details", result.get("bank_details")),
            ("Notes", result.get("notes")),
        ]

        rows = []
        for field_name, value in header_fields:
            present = value is not None and value != "" and value != "N/A"
            rows.append({
                "Field": field_name,
                "Value": str(value) if present else "—",
                "Status": "✅ Extracted" if present else "— Missing",
            })

        df_header = pd.DataFrame(rows)
        st.dataframe(df_header, use_container_width=True, hide_index=True)

        # ── Line items table ──────────────────────────────────────────────
        line_items = result.get("line_items", [])
        st.subheader(f"Line Items ({len(line_items)})")
        if line_items:
            df_items = pd.DataFrame(line_items)
            st.dataframe(df_items, use_container_width=True, hide_index=True)
        else:
            st.info("No line items extracted.")

        # ── Source & method metadata ──────────────────────────────────────
        st.subheader("Source & Method")
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.metric("Source File", meta.get("source_file", "N/A"))
        with col_b:
            st.metric("PDF Type", meta.get("pdf_type", "N/A"))
        with col_c:
            st.metric("OCR Engine", meta.get("ocr_engine", "N/A"))
        with col_d:
            st.metric("Processing Time", f"{meta.get('processing_seconds', '?')}s")

        col_e, col_f, col_g = st.columns(3)
        with col_e:
            st.metric("Pages", meta.get("page_count", "N/A"))
        with col_f:
            st.metric("Tables Found", meta.get("tables_found", "N/A"))
        with col_g:
            st.metric("Text Length", meta.get("text_length", "N/A"))

        # ── Math checks ──────────────────────────────────────────────────
        math = validation.get("math_checks", {})
        if math:
            st.subheader("Math Checks")
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                v = math.get("line_items_sum_to_subtotal")
                label = "✅" if v is True else ("❌" if v is False else "N/A")
                st.metric("Items → Subtotal", label)
            with mc2:
                v = math.get("totals_consistent")
                label = "✅" if v is True else ("❌" if v is False else "N/A")
                st.metric("Totals Consistent", label)
            with mc3:
                line_math = math.get("line_item_math", [])
                all_ok = all(
                    item.get("correct", True) for item in line_math
                ) if line_math else None
                label = "✅" if all_ok is True else ("❌" if all_ok is False else "N/A")
                st.metric("Line Math", label)

        # ── Raw JSON ──────────────────────────────────────────────────────
        with st.expander("📋 Raw JSON"):
            st.json(result)


# ═══════════════════════════════════════════════════════════════════════════
#  Tab 2: Ask a Question
# ═══════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Ask a Question")
    st.markdown(
        "Ask natural-language questions about your invoices. "
        "The system routes your query to the best retrieval strategy automatically."
    )

    question = st.text_input(
        "Your question:",
        placeholder="e.g., What is the total amount of all invoices?",
        key="qa_question_input",
    )

    if st.button("🔍 Ask", type="primary", disabled=not question):
        with st.spinner("Searching and generating answer..."):
            try:
                resp = requests.post(
                    f"{API_URL}/ask",
                    json={"question": question},
                    timeout=120,
                )
                if resp.status_code == 200:
                    data = resp.json()

                    # Answer
                    st.markdown("### Answer")
                    st.info(data.get("answer", "No answer returned."))

                    # Strategy
                    strategy = data.get("strategy", "unknown")
                    reasoning = data.get("reasoning", "")

                    strategy_colors = {
                        "sql": "🗄️ SQL",
                        "bm25": "🔑 BM25 (keyword)",
                        "vector": "🧠 Vector (semantic)",
                        "hybrid": "🔀 Hybrid (BM25 + vector)",
                    }
                    st.markdown(f"**Strategy:** {strategy_colors.get(strategy, strategy)}")
                    st.caption(f"Reasoning: {reasoning}")

                    # Sources
                    sources = data.get("sources", [])
                    if sources:
                        st.markdown("**Source files:**")
                        for src in sources:
                            st.markdown(f"- `{src}`")
                    else:
                        st.markdown("**Source files:** none (aggregation query)")

                    # Context expandable
                    with st.expander("📄 Context used by AI"):
                        st.code(data.get("context_used", ""), language=None)

                    # Add to history
                    st.session_state.qa_history.append({
                        "question": question,
                        "answer": data.get("answer", ""),
                        "strategy": strategy,
                        "sources": sources,
                    })
                else:
                    body = resp.json()
                    st.error(f"**API Error ({resp.status_code}):** {body.get('error', body.get('detail', resp.text))}")
            except requests.ConnectionError:
                st.error("Cannot connect to the API. Is uvicorn running?")
            except Exception as e:
                st.error(f"**Error:** {e}")

    # ── History ───────────────────────────────────────────────────────────
    if st.session_state.qa_history:
        st.markdown("---")
        st.subheader("Q&A History")
        for i, entry in enumerate(reversed(st.session_state.qa_history)):
            with st.expander(f"Q: {entry['question'][:80]}", expanded=(i == 0)):
                st.markdown(entry["answer"])
                st.caption(
                    f"Strategy: {entry.get('strategy', '?')} | "
                    f"Sources: {', '.join(entry.get('sources', [])) or 'none'}"
                )
