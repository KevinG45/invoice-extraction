"""
UI Helper Components for Invoice Extraction Streamlit App.

Provides reusable, styled components for:
- Validation badges with detailed breakdown
- Header fields in card layout
- Line items table with currency formatting
- Financial waterfall charts
- Export functionality (JSON, Excel, CSV)
- Document viewer for PDFs and images
- RAG Q&A enhancements
"""

import base64
import json
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ══════════════════════════════════════════════════════════════════════════════
#  Document Viewer
# ══════════════════════════════════════════════════════════════════════════════

def render_document_viewer(file_bytes: bytes, filename: str, file_type: str):
    """
    Render a document viewer for images or PDFs.

    Args:
        file_bytes: Raw file bytes
        filename: Original filename
        file_type: File extension (pdf, png, jpg, etc.)
    """
    file_type = file_type.lower().replace('.', '')

    if file_type in ['png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp']:
        # Image viewer with zoom control
        zoom = st.slider("Zoom", 50, 200, 100, key=f"zoom_{filename}")
        st.image(file_bytes, caption=filename, width=int(600 * zoom/100))

    elif file_type == 'pdf':
        # PDF iframe viewer
        base64_pdf = base64.b64encode(file_bytes).decode('utf-8')
        pdf_display = f'''
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="800"
            type="application/pdf"
            style="border: 1px solid #ccc; border-radius: 4px;">
        </iframe>
        '''
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.info(f"Preview not available for {file_type} files")




# ══════════════════════════════════════════════════════════════════════════════
#  Header Fields (Card Layout)
# ══════════════════════════════════════════════════════════════════════════════

def render_header_fields(data: Dict):
    """
    Display header fields in grouped card-based layout.

    Args:
        data: Extraction result dictionary
    """
    # ── Vendor Information ──────────────────────────────────────────────
    st.subheader("Vendor Information")
    vendor = data.get("vendor") or {}

    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Name", vendor.get("name", ""), disabled=True, key="vendor_name")
        st.text_input("GSTIN", vendor.get("tax_id", ""), disabled=True, key="vendor_tax_id")
    with col2:
        st.text_area("Address", vendor.get("address", ""), disabled=True, height=100, key="vendor_address")
        col_email, col_phone = st.columns(2)
        with col_email:
            st.text_input("Email", vendor.get("email", ""), disabled=True, key="vendor_email")
        with col_phone:
            st.text_input("Phone", vendor.get("phone", ""), disabled=True, key="vendor_phone")

    # ── Customer Information ────────────────────────────────────────────
    st.subheader("Customer Information")
    bill_to = data.get("bill_to") or {}

    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Name", bill_to.get("name", ""), disabled=True, key="customer_name")
        st.text_input("Tax ID", bill_to.get("tax_id", ""), disabled=True, key="customer_tax_id")
    with col2:
        st.text_area("Address", bill_to.get("address", ""), disabled=True, height=100, key="customer_address")
        col_email, col_phone = st.columns(2)
        with col_email:
            st.text_input("Email", bill_to.get("email", ""), disabled=True, key="customer_email")
        with col_phone:
            st.text_input("Phone", bill_to.get("phone", ""), disabled=True, key="customer_phone")

    # ── Invoice Details ─────────────────────────────────────────────────
    # FIXED: Bug P0-2 — Clean section header
    st.subheader("Invoice Details")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.text_input("Invoice #", data.get("invoice_number", ""), disabled=True, key="invoice_number")
    with col2:
        inv_date = data.get("invoice_date", "")
        st.text_input("Date", inv_date, disabled=True, key="invoice_date")
    with col3:
        due_date = data.get("due_date", "")
        st.text_input("Due Date", due_date if due_date else "—", disabled=True, key="due_date")
    with col4:
        st.text_input("PO #", data.get("purchase_order_number", ""), disabled=True, key="po_number")

    col5, col6, col7 = st.columns(3)
    with col5:
        st.text_input("Currency", data.get("currency", "INR"), disabled=True, key="currency")
    with col6:
        st.text_input("Payment Terms", data.get("payment_terms", ""), disabled=True, key="payment_terms")
    with col7:
        st.text_input("Payment Method", data.get("payment_method", ""), disabled=True, key="payment_method")


# ══════════════════════════════════════════════════════════════════════════════
#  Line Items Table (Styled)
# ══════════════════════════════════════════════════════════════════════════════

def render_line_items_table(line_items: List[Dict]):
    """
    Display line items in a currency-formatted dataframe.

    Args:
        line_items: List of line item dictionaries
    """
    if not line_items:
        st.info("No line items found")
        return

    df = pd.DataFrame(line_items)

    # Format currency columns
    for col in ["unit_price", "total", "line_total", "discount"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) and x != "" else "—")

    # Format quantity
    if "quantity" in df.columns:
        df["quantity"] = df["quantity"].apply(lambda x: f"{float(x):.2f}" if pd.notna(x) and x != "" else "—")

    # Display with styling
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "description": st.column_config.TextColumn("Description", width="large"),
            "quantity": st.column_config.TextColumn("Qty", width="small"),
            "unit": st.column_config.TextColumn("Unit", width="small"),
            "unit_price": st.column_config.TextColumn("Unit Price", width="medium"),
            "total": st.column_config.TextColumn("Total", width="medium"),
            "line_total": st.column_config.TextColumn("Line Total", width="medium"),
        }
    )

    # Summary row
    total_sum = 0
    for item in line_items:
        # FIXED: Bug UI-2 — Check if item is dict before accessing
        if not isinstance(item, dict):
            continue
        # Handle both 'total' and 'line_total' keys
        total_val = item.get("total") or item.get("line_total", 0)
        if total_val:
            try:
                total_sum += float(total_val)
            except (ValueError, TypeError):
                pass  # Skip invalid values

    st.markdown(f"**Total Line Items:** {len(line_items)} | **Sum:** {total_sum:,.2f}")


# ══════════════════════════════════════════════════════════════════════════════
#  Financial Waterfall Chart
# ══════════════════════════════════════════════════════════════════════════════

def render_financial_waterfall(data: Dict):
    """
    Display waterfall chart: subtotal → +tax → -discount → +shipping → total.

    Args:
        data: Extraction result dictionary
    """
    subtotal = float(data.get("subtotal") or 0)
    tax = float(data.get("tax_amount") or 0)
    discount = -(float(data.get("discount") or 0))  # Negative
    shipping = float(data.get("shipping") or 0)
    total = float(data.get("total_amount") or 0)

    # Only show if we have meaningful data
    if subtotal == 0 and total == 0:
        return

    fig = go.Figure(go.Waterfall(
        name="Financial Breakdown",
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["Subtotal", "Tax", "Discount", "Shipping", "Total"],
        y=[subtotal, tax, discount, shipping, total],
        text=[f"₹{subtotal:,.2f}", f"+₹{tax:,.2f}", f"₹{discount:,.2f}", f"+₹{shipping:,.2f}", f"₹{total:,.2f}"],
        textposition="outside",
        connector={"line": {"color": "rgb(63, 63, 63)"}},
    ))

    fig.update_layout(
        title="Financial Breakdown",
        showlegend=False,
        height=400,
        yaxis_title="Amount (₹)",
    )

    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Processing Timeline
# ══════════════════════════════════════════════════════════════════════════════

def render_processing_timeline(metadata: Dict):
    """
    Show processing time and other metadata metrics.

    Args:
        metadata: Metadata object from extraction result
    """
    processing_time = metadata.get("processing_seconds", 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Processing Time", f"{processing_time:.1f}s")
    with col2:
        st.metric("OCR Engine", metadata.get("ocr_engine", "N/A"))
    with col3:
        st.metric("PDF Type", metadata.get("pdf_type", "N/A"))
    with col4:
        st.metric("Pages", metadata.get("page_count", "N/A"))


# ══════════════════════════════════════════════════════════════════════════════
#  Export Functions
# ══════════════════════════════════════════════════════════════════════════════

def create_json_export(data: Dict, invoice_number: str) -> tuple[bytes, str]:
    """
    Create JSON export of extraction results.

    Returns:
        (json_bytes, filename)
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    filename = f"{invoice_number}_extraction.json" if invoice_number else "extraction.json"
    return json_str.encode('utf-8'), filename


def create_excel_export(data: Dict, invoice_number: str) -> tuple[bytes, str]:
    """
    Create Excel export with 2 sheets: Header + Line Items.

    Returns:
        (excel_bytes, filename)
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Header fields (vertical layout)
        vendor = data.get("vendor") or {}
        bill_to = data.get("bill_to") or {}

        header_data = {
            "Field": [
                "Invoice Number", "Invoice Date", "Due Date", "PO Number",
                "Vendor Name", "Vendor Tax ID", "Vendor Address", "Vendor Email", "Vendor Phone",
                "Customer Name", "Customer Tax ID", "Customer Address",
                "Subtotal", "Tax Rate", "Tax Amount", "Discount", "Shipping",
                "Total Amount", "Amount Paid", "Amount Due",
                "Currency", "Payment Terms", "Payment Method"
            ],
            "Value": [
                data.get("invoice_number"),
                data.get("invoice_date"),
                data.get("due_date"),
                data.get("purchase_order_number"),
                vendor.get("name"),
                vendor.get("tax_id"),
                vendor.get("address"),
                vendor.get("email"),
                vendor.get("phone"),
                bill_to.get("name"),
                bill_to.get("tax_id"),
                bill_to.get("address"),
                data.get("subtotal"),
                data.get("tax_rate"),
                data.get("tax_amount"),
                data.get("discount"),
                data.get("shipping"),
                data.get("total_amount"),
                data.get("amount_paid"),
                data.get("amount_due"),
                data.get("currency"),
                data.get("payment_terms"),
                data.get("payment_method"),
            ]
        }
        pd.DataFrame(header_data).to_excel(writer, sheet_name="Header", index=False)

        # Sheet 2: Line items
        line_items = data.get("line_items", [])
        if line_items:
            pd.DataFrame(line_items).to_excel(writer, sheet_name="Line Items", index=False)

    filename = f"{invoice_number}_extraction.xlsx" if invoice_number else "extraction.xlsx"
    return output.getvalue(), filename


def create_csv_export(line_items: List[Dict], invoice_number: str) -> tuple[str, str]:
    """
    Create CSV export of line items only.

    Returns:
        (csv_string, filename)
    """
    if not line_items:
        return "", ""

    df = pd.DataFrame(line_items)
    csv = df.to_csv(index=False)
    filename = f"{invoice_number}_line_items.csv" if invoice_number else "line_items.csv"
    return csv, filename


def render_export_buttons(data: Dict):
    """
    Show 3 export buttons: JSON, Excel, CSV.

    Args:
        data: Extraction result dictionary
    """
    invoice_number = data.get("invoice_number", "invoice")
    # Clean invoice number for filename
    invoice_number = "".join(c for c in str(invoice_number) if c.isalnum() or c in "-_")

    col1, col2, col3 = st.columns(3)

    with col1:
        # JSON export
        json_bytes, json_filename = create_json_export(data, invoice_number)
        st.download_button(
            label="📥 Download JSON",
            data=json_bytes,
            file_name=json_filename,
            mime="application/json",
            use_container_width=True
        )

    with col2:
        # Excel export
        excel_bytes, excel_filename = create_excel_export(data, invoice_number)
        st.download_button(
            label="📥 Download Excel",
            data=excel_bytes,
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col3:
        # CSV export
        line_items = data.get("line_items", [])
        if line_items:
            csv_str, csv_filename = create_csv_export(line_items, invoice_number)
            st.download_button(
                label="📥 Download CSV",
                data=csv_str,
                file_name=csv_filename,
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("📥 Download CSV", disabled=True, use_container_width=True,
                     help="No line items to export")


# ══════════════════════════════════════════════════════════════════════════════
#  RAG Q&A Enhancements
# ══════════════════════════════════════════════════════════════════════════════

def render_query_suggestions():
    """
    Display clickable query suggestion buttons.

    Returns:
        Selected suggestion text or None
    """
    st.subheader("Example Questions")

    suggestions = [
        "How many invoices are in the system?",
        "Show me invoice GST001",
        "What is the total tax amount?",
        "Tell me about NIREL DIGITALS",
        "Show invoices similar to printing services",
        "What payment methods are used?",
    ]

    cols = st.columns(3)
    selected = None

    for i, suggestion in enumerate(suggestions):
        with cols[i % 3]:
            if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                selected = suggestion

    return selected


def render_confidence_indicator(rag_result: Dict):
    """
    Display confidence level based on strategy and reranking.

    Args:
        rag_result: RAG response dictionary
    """
    # FIXED: Bug UI-3 — Check if rag_result is None
    if not rag_result or not isinstance(rag_result, dict):
        st.info("Strategy: **Unknown** | Confidence: **Unknown**")
        return
    
    strategy = rag_result.get("strategy", "")
    reranked = rag_result.get("reranked", False)

    # Determine confidence level
    if strategy == "sql":
        confidence = "Very High (Exact Query)"
        color = "green"
    elif reranked:
        confidence = "High (Re-ranked)"
        color = "green"
    elif strategy in ["bm25", "hybrid"]:
        confidence = "Medium-High"
        color = "blue"
    else:
        confidence = "Medium"
        color = "orange"

    # FIXED: Bug P0-2 — Clean strategy labels
    strategy_labels = {
        "sql": "SQL Query",
        "bm25": "BM25 Keyword",
        "vector": "Vector Search",
        "hybrid": "Hybrid Search",
    }

    st.info(f"Strategy: **{strategy_labels.get(strategy, strategy)}** | Confidence: **{confidence}**")


def render_source_previews(sources: List[str], api_url: str):
    """
    Show expandable source document previews.

    Args:
        sources: List of source filenames
        api_url: API base URL
    """
    # FIXED: Bug UI-1 — Check if sources is None, not just falsy
    if sources is None or not sources:
        return

    # FIXED: Bug P0-2 — Clean section header
    st.subheader("Sources")
    for source in sources[:5]:  # Limit to top 5
        with st.expander(f"{source}"):
            st.caption(f"Source document: {source}")
            st.markdown("*Preview functionality can be extended to show key fields*")
