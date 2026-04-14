"""
Generates two PDFs for the AI-Powered Invoice Extraction System presentation:
  1. presentation_updated.pdf  — slide-style deck for evaluators
  2. qa_prep.pdf               — term definitions + likely evaluator Q&A
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
from reportlab.lib.colors import HexColor
import os

# ── Brand colours ─────────────────────────────────────────────────────────────
CHRIST_BLUE   = HexColor("#003B6F")
CHRIST_GOLD   = HexColor("#C9A84C")
SLIDE_BG      = colors.white
BODY_TEXT     = HexColor("#1A1A1A")
ACCENT_BLUE   = HexColor("#0055A5")
LIGHT_GREY    = HexColor("#F2F4F7")

LANDSCAPE = (297*mm, 210*mm)  # A4 landscape for slides
PORTRAIT  = A4                 # A4 portrait for Q&A doc

OUTPUT_DIR = r"c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current"

# ══════════════════════════════════════════════════════════════════════════════
#  SLIDE PDF
# ══════════════════════════════════════════════════════════════════════════════

def build_slide_pdf():
    path = os.path.join(OUTPUT_DIR, "presentation_updated.pdf")

    # ── page callbacks ─────────────────────────────────────────────────────
    def on_page(canvas, doc):
        W, H = LANDSCAPE
        # top blue banner
        canvas.setFillColor(CHRIST_BLUE)
        canvas.rect(0, H - 22*mm, W, 22*mm, fill=1, stroke=0)
        # gold accent strip under banner
        canvas.setFillColor(CHRIST_GOLD)
        canvas.rect(0, H - 23.5*mm, W, 1.5*mm, fill=1, stroke=0)
        # bottom blue footer
        canvas.setFillColor(CHRIST_BLUE)
        canvas.rect(0, 0, W, 14*mm, fill=1, stroke=0)
        # footer text
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(10*mm, 5*mm, "CHRIST (Deemed to be University)")
        canvas.setFillColor(CHRIST_GOLD)
        canvas.setFont("Helvetica-Oblique", 8)
        canvas.drawRightString(W - 10*mm, 5*mm, "Excellence & Service")
        # page number
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(W / 2, 5*mm, str(doc.page))

    frame = Frame(
        15*mm, 18*mm,          # x, y (above footer)
        267*mm, 165*mm,        # width, height (below banner)
        leftPadding=0, rightPadding=0,
        topPadding=5*mm, bottomPadding=0,
        id="main"
    )
    template = PageTemplate(id="slide", frames=[frame], onPage=on_page)

    doc = BaseDocTemplate(
        path,
        pagesize=LANDSCAPE,
        pageTemplates=[template],
        leftMargin=0, rightMargin=0,
        topMargin=0, bottomMargin=0,
    )

    # ── styles ─────────────────────────────────────────────────────────────
    def S(name, parent="Normal", **kw):
        s = ParagraphStyle(name, parent=getSampleStyleSheet()[parent], **kw)
        return s

    sTitle     = S("sTitle",    fontSize=28, textColor=BODY_TEXT,   leading=34, spaceBefore=20, spaceAfter=6,  fontName="Helvetica-Bold",  alignment=TA_CENTER)
    sSubtitle  = S("sSubtitle", fontSize=14, textColor=ACCENT_BLUE, leading=18, spaceBefore=6,  spaceAfter=4,  fontName="Helvetica",       alignment=TA_CENTER)
    sPresenter = S("sPres",     fontSize=12, textColor=BODY_TEXT,   leading=16, spaceBefore=4,  spaceAfter=2,  fontName="Helvetica",       alignment=TA_CENTER)
    sH1        = S("sH1",       fontSize=20, textColor=CHRIST_BLUE, leading=26, spaceBefore=4,  spaceAfter=6,  fontName="Helvetica-Bold")
    sH2        = S("sH2",       fontSize=13, textColor=CHRIST_BLUE, leading=18, spaceBefore=8,  spaceAfter=3,  fontName="Helvetica-Bold")
    sBody      = S("sBody",     fontSize=11, textColor=BODY_TEXT,   leading=16, spaceBefore=2,  spaceAfter=2,  fontName="Helvetica",       leftIndent=0)
    sBullet    = S("sBullet",   fontSize=11, textColor=BODY_TEXT,   leading=16, spaceBefore=3,  spaceAfter=2,  fontName="Helvetica",       leftIndent=14, bulletIndent=4)
    sBullet2   = S("sBullet2",  fontSize=10, textColor=BODY_TEXT,   leading=14, spaceBefore=2,  spaceAfter=1,  fontName="Helvetica",       leftIndent=28, bulletIndent=18)
    sNote      = S("sNote",     fontSize=9,  textColor=HexColor("#555555"), leading=12, spaceBefore=2, spaceAfter=2, fontName="Helvetica-Oblique")
    sBig       = S("sBig",      fontSize=14, textColor=CHRIST_BLUE, leading=20, spaceBefore=6,  spaceAfter=4,  fontName="Helvetica-Bold",  alignment=TA_CENTER)

    def bullet(text, level=1, bold_prefix=None):
        marker = "•"
        if bold_prefix:
            text = f"<b>{bold_prefix}</b> – {text}"
        return Paragraph(f"{marker}  {text}", sBullet if level == 1 else sBullet2)

    def hr():
        return HRFlowable(width="100%", thickness=1, color=CHRIST_GOLD, spaceAfter=4, spaceBefore=4)

    story = []

    # ── SLIDE 1: Title ─────────────────────────────────────────────────────
    story += [
        Spacer(1, 30*mm),
        Paragraph("AI-Powered Invoice Extraction System", sTitle),
        hr(),
        Paragraph("Presented by:", sSubtitle),
        Paragraph("Kevin George (2448030)", sPresenter),
        Spacer(1, 6*mm),
        Paragraph("Department of Computer Science &amp; Engineering", sNote),
        Paragraph("CHRIST (Deemed to be University), Bangalore", sNote),
        PageBreak(),
    ]

    # ── SLIDE 2: Problem & Application Domain ──────────────────────────────
    story += [
        Paragraph("Problem &amp; Application Domain", sH1), hr(),
        Paragraph("Application Domain", sH2),
        Paragraph("Supply Chain &amp; Finance Document Processing", sBody),
        Spacer(1, 4*mm),
        Paragraph("Problem", sH2),
        bullet("Businesses receive invoices in multiple formats (PDF, scanned, image) — no single automated tool handles all"),
        bullet("Manual data entry is slow, error-prone, and costly at scale"),
        bullet("Indian GST invoices add complexity: CGST/SGST/IGST splits, GSTIN validation, HSN codes"),
        bullet("No queryable, structured invoice database exists — past invoices cannot be searched or audited efficiently"),
        PageBreak(),
    ]

    # ── SLIDE 3: Technological Domain ──────────────────────────────────────
    story += [
        Paragraph("Technological Domain", sH1), hr(),
        Paragraph("AI-Based Document Intelligence &amp; Financial Entity Extraction", sBody),
        Spacer(1, 3*mm),
        Paragraph("Core Technologies Implemented:", sH2),
        bullet("OCR-based text extraction", bold_prefix="Tesseract OCR"),
        bullet("EasyOCR for vendor logo / company name recognition from image headers", bold_prefix="EasyOCR"),
        bullet("Structured field parsing using compiled pattern libraries", bold_prefix="Regex Engine"),
        bullet("Local LLM (qwen2.5:3b via Ollama) for free-text & ambiguous field extraction", bold_prefix="LLM Extraction"),
        bullet("BM25 full-text search over extracted invoice corpus", bold_prefix="RAG / BM25 Search"),
        bullet("FastAPI REST interface with auto-indexing of each processed invoice", bold_prefix="REST API"),
        bullet("Rule-based checks: GSTIN format, tax arithmetic, subtotal vs line-item sum", bold_prefix="Validation Framework"),
        PageBreak(),
    ]

    # ── SLIDE 4: System Architecture ───────────────────────────────────────
    story += [
        Paragraph("System Architecture", sH1), hr(),
        Paragraph("6-Stage Extraction Pipeline  (core/pipeline.py)", sH2),
        Spacer(1, 3*mm),
    ]

    pipeline_data = [
        ["Stage", "Name", "What it does"],
        ["1", "Document Loader",    "Detects file type (digital PDF / scanned PDF / image)"],
        ["2", "Text Extractor",     "pdfplumber for digital PDFs; Tesseract OCR for images & scanned"],
        ["3", "LLM Field Extractor","Ollama (qwen2.5:3b) extracts all header fields in one JSON call"],
        ["4a–4d", "Post-Processing","Regex backfill · vendor logo OCR · customer name cleanup · currency fix"],
        ["5", "Validation",         "GSTIN check · tax arithmetic · subtotal vs line-item sum · surcharge-aware"],
        ["6", "Export",             "JSON file + BM25 index update; REST API serves results"],
    ]
    col_w = [18*mm, 42*mm, 175*mm]
    t = Table(pipeline_data, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), CHRIST_BLUE),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 9),
        ("FONTSIZE",     (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT_GREY, colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
    ]))
    story += [t, Spacer(1, 5*mm),
              Paragraph("Input → OCR/PDF Parse → LLM Extract → Regex Backfill → Validate → JSON + API", sBig),
              PageBreak()]

    # ── SLIDE 5: Data & Extraction Strategy ────────────────────────────────
    story += [
        Paragraph("Data &amp; Extraction Strategy", sH1), hr(),
        Paragraph("Input Formats Supported", sH2),
        bullet("Digital PDFs — text layer extracted directly via pdfplumber (fast, lossless)"),
        bullet("Scanned PDFs &amp; image invoices (JPEG, PNG, TIFF, BMP) — rendered to image, preprocessed, then Tesseract OCR"),
        Spacer(1, 3*mm),
        Paragraph("Dual-Path OCR Processing", sH2),
        bullet("Image preprocessing: greyscale conversion, adaptive thresholding, conditional 2× upscaling (only if width &lt; 1800 px)"),
        bullet("Tesseract with custom config (--psm 6, digit cleaning: O→0, l→1, spaces-between-digits)"),
        bullet("EasyOCR as fallback specifically for vendor name detection from the invoice header / logo region"),
        Spacer(1, 3*mm),
        Paragraph("Test Dataset", sH2),
        bullet("45+ real Indian GST invoices (PDF &amp; image formats)"),
        bullet("Formats covered: SleekBill, Tally, custom ERP exports, hand-typed scanned invoices"),
        PageBreak(),
    ]

    # ── SLIDE 6: Hybrid Field & Table Extraction ────────────────────────────
    story += [
        Paragraph("Hybrid Field &amp; Table Extraction", sH1), hr(),
        Paragraph("Header Fields Extracted (14 fields)", sH2),
        Paragraph("invoice_number · invoice_date · due_date · vendor_name · vendor_gstin · vendor_address · bill_to.name · bill_to.address · bill_to.gstin · subtotal · tax_amount · tax_rate · total_amount · currency", sBody),
        Spacer(1, 4*mm),
        Paragraph("Extraction Strategy — Three Layers", sH2),
        bullet("Primary pass: Ollama LLM (qwen2.5:3b) receives full invoice text + structured JSON prompt; returns all fields in one call with <b>format=json</b> enforced", level=1),
        bullet("Backfill pass: Regex patterns fix or override specific fields the LLM missed or got wrong (GSTIN, amounts, CGST/SGST, currency)", level=1),
        bullet("Derive pass: If tax not found, derive tax = total − subtotal; if currency null but GSTIN present → force INR", level=1),
        Spacer(1, 3*mm),
        Paragraph("Line Item Extraction", sH2),
        bullet("pdfplumber table extraction for digital PDFs (exact cell coordinates)"),
        bullet("Regex pattern matching for scanned invoices (HSN, qty, unit price, line total)"),
        bullet("clean_ocr_number() normalises OCR noise in numeric fields before parsing"),
        PageBreak(),
    ]

    # ── SLIDE 7: Validation Framework ──────────────────────────────────────
    story += [
        Paragraph("Validation Framework", sH1), hr(),
        Paragraph("Five Automated Checks (core/validator.py)", sH2),
        Spacer(1, 3*mm),
    ]
    checks = [
        ["Check", "Description"],
        ["1 · GSTIN Format",       "15-char alphanumeric pattern; state code verified against known list"],
        ["2 · Tax Arithmetic",      "tax_amount ≈ subtotal × tax_rate/100  (±0.5% tolerance)"],
        ["3 · Total Consistency",   "total_amount ≈ subtotal + tax_amount  (±0.5% tolerance)"],
        ["4 · Line-Item Subtotal",  "sum(line_totals) ≈ subtotal; shipping/freight lines excluded automatically"],
        ["5 · Date Logic",          "invoice_date ≤ due_date; neither date in the future beyond 1 year"],
    ]
    tc = Table(checks, colWidths=[50*mm, 185*mm])
    tc.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), CHRIST_BLUE),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT_GREY, colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story += [tc, Spacer(1, 5*mm),
              Paragraph("All checks produce a pass/fail flag + human-readable warning message stored in the JSON output.", sNote),
              PageBreak()]

    # ── SLIDE 8: REST API & Search ──────────────────────────────────────────
    story += [
        Paragraph("REST API &amp; Invoice Search", sH1), hr(),
        Paragraph("FastAPI Backend (api/main.py)", sH2),
        bullet("POST /extract — upload invoice file → returns full JSON extraction result"),
        bullet("GET  /invoices — list all processed invoices"),
        bullet("GET  /search?q=... — BM25 full-text search across all extracted invoice data"),
        bullet("GET  /invoice/{id} — fetch a specific invoice's extracted JSON"),
        Spacer(1, 4*mm),
        Paragraph("BM25 Search Engine (rag/bm25_retriever.py)", sH2),
        bullet("Indexes vendor name, GSTIN, invoice number, bill-to name for every processed invoice"),
        bullet("Incremental updates: each new extraction adds to the index without full rebuild"),
        bullet("Enables queries like: 'find all invoices from vendor X' or 'invoices with GSTIN 29AAA...'"),
        Spacer(1, 4*mm),
        Paragraph("Web Frontend", sH2),
        bullet("React-based UI — drag-and-drop upload, live extraction results, search interface"),
        PageBreak(),
    ]

    # ── SLIDE 9: System Outputs ─────────────────────────────────────────────
    story += [
        Paragraph("System Outputs", sH1), hr(),
        Paragraph("JSON Extraction Report", sH2),
        bullet("All 14 header fields with extracted values"),
        bullet("Line-item array: description, HSN, qty, unit_price, total per item"),
        bullet("Validation result: passed (True/False) + list of warnings"),
        bullet("Processing time and PDF type (digital / scanned / image)"),
        Spacer(1, 3*mm),
        Paragraph("Excel Workbook", sH2),
        bullet("Sheet 1: Invoice Headers — one row per invoice"),
        bullet("Sheet 2: Line Items — one row per line item, linked by invoice ID"),
        bullet("ERP-ready structured format for import into SAP, Tally, Zoho"),
        Spacer(1, 3*mm),
        Paragraph("BM25 Search Index", sH2),
        bullet("Persistent index file updated after every extraction"),
        bullet("Supports real-time search from the REST API and web UI"),
        PageBreak(),
    ]

    # ── SLIDE 10: Test Results ──────────────────────────────────────────────
    story += [
        Paragraph("Test Results", sH1), hr(),
        Paragraph("Key Invoice Test Cases", sH2),
        Spacer(1, 3*mm),
    ]
    results = [
        ["Invoice",     "Type",    "Time",  "Pass?", "Notes"],
        ["GST001.pdf",  "Digital PDF",  "46s",  "✓ Pass", "All 14 fields correct, 0 warnings"],
        ["GST003.pdf",  "Digital PDF",  "35s",  "✓ Pass", "CGST/SGST parenthesis format handled"],
        ["GST004.pdf",  "Digital PDF",  "52s",  "✓ Pass", "3 line items all correct"],
        ["invis1.jpg",  "Image (JPG)",  "97s",  "Partial", "Currency & bill_to fixed; line items need OCR improvement"],
    ]
    tr = Table(results, colWidths=[35*mm, 32*mm, 18*mm, 22*mm, 128*mm])
    tr.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), CHRIST_BLUE),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [LIGHT_GREY, colors.white]),
        ("GRID",         (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("TEXTCOLOR",    (4, 1), (4, 3), HexColor("#006600")),
        ("TEXTCOLOR",    (4, 4), (4, 4), HexColor("#AA5500")),
    ]))
    story += [tr, Spacer(1, 5*mm),
              Paragraph("LLM response time improved from ~90s (3 retries) to ~45s (0 retries) after adding format:json to Ollama payload.", sNote),
              PageBreak()]

    # ── SLIDE 11: Conclusion ────────────────────────────────────────────────
    story += [
        Paragraph("Conclusion", sH1), hr(),
        Paragraph("What Was Built", sH2),
        bullet("End-to-end invoice extraction system handling digital PDFs, scanned PDFs, and image invoices"),
        bullet("Hybrid extraction: Regex (speed + precision for structured fields) + LLM (flexibility for free-text)"),
        bullet("Indian GST compliance: GSTIN validation, CGST/SGST/IGST handling, surcharge-aware subtotal checks"),
        bullet("REST API with BM25 search — invoices are immediately queryable after extraction"),
        Spacer(1, 4*mm),
        Paragraph("Key Design Decisions", sH2),
        bullet("Local-only LLM (Ollama) — no cloud API dependency, data stays on-premise"),
        bullet("Regex backfill on top of LLM — handles LLM hallucinations / missed fields deterministically"),
        bullet("format=json enforced in Ollama payload — eliminated 3× retry loop, cut LLM time by ~50%"),
        Spacer(1, 4*mm),
        Paragraph("Future Scope", sH2),
        bullet("Full PPStructure table parsing (requires Python ≤ 3.12 + paddlepaddle)"),
        bullet("Pre-tax vs post-tax line_total detection for accurate unit price back-calculation"),
    ]

    doc.build(story)
    print(f"[✓] Slide PDF saved: {path}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
#  Q&A PREP PDF
# ══════════════════════════════════════════════════════════════════════════════

def build_qa_pdf():
    path = os.path.join(OUTPUT_DIR, "qa_prep.pdf")

    doc = SimpleDocTemplate(
        path,
        pagesize=PORTRAIT,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=22*mm, bottomMargin=22*mm,
    )

    styles = getSampleStyleSheet()

    def S(name, parent="Normal", **kw):
        return ParagraphStyle(name, parent=styles[parent], **kw)

    sDocTitle  = S("dT",  fontSize=18, textColor=CHRIST_BLUE, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
    sSub       = S("dS",  fontSize=11, textColor=ACCENT_BLUE, fontName="Helvetica",      alignment=TA_CENTER, spaceAfter=12)
    sSection   = S("sec", fontSize=14, textColor=CHRIST_BLUE, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4, borderPad=2)
    sTerm      = S("trm", fontSize=11, textColor=CHRIST_BLUE, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=2)
    sDefn      = S("def", fontSize=10, textColor=BODY_TEXT,   fontName="Helvetica",      leading=15, spaceAfter=2, leftIndent=10)
    sQ         = S("q",   fontSize=11, textColor=HexColor("#5C3317"), fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=3, leftIndent=6)
    sA         = S("a",   fontSize=10, textColor=BODY_TEXT,   fontName="Helvetica",      leading=15, spaceAfter=4, leftIndent=14)
    sNote2     = S("n2",  fontSize=9,  textColor=HexColor("#666666"), fontName="Helvetica-Oblique", spaceAfter=6)

    def hr2(col=CHRIST_GOLD):
        return HRFlowable(width="100%", thickness=1.2, color=col, spaceAfter=6, spaceBefore=2)

    def section(title):
        return [Paragraph(title, sSection), hr2()]

    def term(t, defn):
        return [Paragraph(t, sTerm), Paragraph(defn, sDefn)]

    def qa(q, a):
        return [Paragraph(f"Q: {q}", sQ), Paragraph(f"A: {a}", sA)]

    story = []

    # ── Cover ───────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 10*mm),
        Paragraph("AI-Powered Invoice Extraction System", sDocTitle),
        Paragraph("Evaluator Q&amp;A Preparation Guide", sSub),
        HRFlowable(width="100%", thickness=2, color=CHRIST_BLUE, spaceAfter=8),
        Paragraph("This document has two parts: (1) plain-English definitions of every technical term in the project, and (2) likely evaluator questions with complete, spoken-language answers.", sDefn),
        Spacer(1, 6*mm),
    ]

    # ══════════════════════════════════════════════════════════════════════
    # PART 1 — TERM DEFINITIONS
    # ══════════════════════════════════════════════════════════════════════
    story += section("Part 1 — Key Terms Explained")

    story += term("OCR — Optical Character Recognition",
        "Software that looks at an image of text (like a photo of a printed invoice) and converts it into machine-readable characters. "
        "Without OCR you only have a picture; with OCR you have actual text you can process. Think of it as a digital reader for printed words.")

    story += term("Tesseract OCR",
        "An open-source OCR engine originally built by HP, now maintained by Google. It is the primary OCR tool in this project. "
        "Before feeding the image to Tesseract we preprocess it — converting to greyscale, increasing contrast, and upscaling small images — "
        "so Tesseract reads the text more accurately.")

    story += term("EasyOCR",
        "A Python library for OCR that works especially well on images with mixed fonts and logos. "
        "In this project EasyOCR is used only as a fallback to try to read the vendor company name from the logo region at the top of image invoices, "
        "because the company name is often embedded inside a graphical logo that Tesseract struggles with.")

    story += term("pdfplumber",
        "A Python library that extracts text and table data directly from the internal structure of a digital PDF — no OCR needed. "
        "If a PDF was created by software (not scanned), pdfplumber can read exact characters and table cell positions. "
        "This is much faster and more accurate than OCR for digital PDFs.")

    story += term("Regex — Regular Expressions",
        "A pattern-matching language. You write a template like 'two letters, two digits, four letters, one letter, three digits, one letter, two digits' "
        "and the regex engine finds anything in the text that matches that pattern. "
        "In this project regex is used to find GSTIN numbers, rupee amounts, dates, and tax percentages, because these always follow a predictable format.")

    story += term("LLM — Large Language Model",
        "An AI model trained on vast amounts of text that can understand and generate natural language. "
        "It can answer questions, summarise text, and extract information from unstructured paragraphs. "
        "In this project an LLM is used to extract fields like vendor name and billing address that do not follow a fixed pattern and would be hard to capture with regex alone.")

    story += term("Ollama",
        "A tool that lets you run open-source LLMs locally on your own computer without an internet connection. "
        "It downloads model files and serves them through a simple local API. "
        "This means the invoice data never leaves the machine — important for privacy and compliance.")

    story += term("qwen2.5:3b",
        "The specific LLM model used in this project. 'qwen2.5' is the model family (made by Alibaba), '3b' means it has 3 billion parameters. "
        "It is small enough to run on a laptop with 8 GB RAM, responds in ~45 seconds, and produces clean JSON output when given a structured prompt. "
        "Larger models like llama3 (8b) were tested but timed out on the available hardware.")

    story += term("format:json (Ollama feature)",
        "When you add 'format: json' to an Ollama API call, the model is forced to produce valid JSON and nothing else — no explanation text, "
        "no 'here is the answer:', just the raw JSON object. This eliminated the need for retries (previously ~3 retries × 30s = 90s wasted) "
        "and cut extraction time nearly in half.")

    story += term("RAG — Retrieval Augmented Generation",
        "A technique where, instead of asking an AI to remember everything, you first retrieve relevant documents from a database, "
        "then feed those documents to the AI along with the question. "
        "In this project the term is used loosely — BM25 retrieval is the 'R' part, returning matching invoices from the stored corpus.")

    story += term("BM25 — Best Match 25",
        "A classic text-search ranking algorithm (the same family as what Google originally used). "
        "It scores documents by how often the search terms appear, weighted by how rare those terms are across the whole corpus. "
        "In this project BM25 indexes every extracted invoice's vendor name, GSTIN, invoice number, and bill-to name, "
        "so a user can search 'find all invoices from Infosys' and get ranked results instantly.")

    story += term("FastAPI",
        "A modern Python web framework for building REST APIs. It is fast, generates automatic API documentation, "
        "and handles file uploads cleanly. The project uses FastAPI to expose endpoints: POST /extract (upload a file), "
        "GET /search (search invoices), GET /invoices (list all), GET /invoice/{id} (get one).")

    story += term("REST API",
        "A standard way for software systems to communicate over HTTP. "
        "REST APIs use URLs and HTTP methods (POST, GET, DELETE) to perform operations. "
        "The project's REST API means any other system (ERP, Excel macro, mobile app) can send an invoice file and receive structured data back — "
        "no manual steps required.")

    story += term("Pipeline",
        "A sequence of processing stages where the output of one stage becomes the input of the next. "
        "This project's pipeline has 6 stages: load document → extract text → LLM field extraction → post-processing → validation → export. "
        "Each stage does one job, making it easy to debug and improve independently.")

    story += term("GSTIN — Goods and Services Tax Identification Number",
        "A 15-character alphanumeric code assigned to every GST-registered business in India. "
        "Format: 2-digit state code + 10-digit PAN + 1 entity digit + 'Z' + 1 check digit. "
        "This project validates GSTIN format using regex and verifies the state code.")

    story += term("CGST / SGST / IGST",
        "The three types of GST in India. CGST (Central GST) and SGST (State GST) are both applied on intra-state transactions, "
        "each at half the total rate. IGST (Integrated GST) is applied on inter-state transactions at the full rate. "
        "The system detects which type is present on each invoice and maps them correctly to tax_amount.")

    story += term("HSN Code — Harmonised System of Nomenclature",
        "A standardised 6-8 digit code that classifies every physical product for GST purposes. "
        "Each line item on an Indian GST invoice should have an HSN code. The system extracts HSN codes as part of line-item parsing.")

    story += term("Confidence Score",
        "A number (0–1) indicating how sure the system is about a particular extracted value. "
        "High confidence (close to 1) means the value was found by a reliable method like direct PDF text extraction or a strong regex match. "
        "Low confidence means the LLM guessed it from context and it may need human review.")

    story += term("Validation Framework",
        "A set of automated checks run after extraction to verify that the extracted numbers make mathematical sense. "
        "For example: does subtotal × tax_rate = tax_amount? Does subtotal + tax = total? "
        "These checks catch OCR errors or LLM hallucinations before the data reaches a downstream system.")

    story += term("Surcharge-Aware Subtotal Check",
        "Some invoices include a shipping or freight charge as a separate line item that is NOT part of the product subtotal. "
        "A naive check would fail because sum(line_totals) > subtotal. "
        "The system detects lines matching patterns like 'shipping', 'freight', 'packing' with no HSN code and excludes them from the subtotal comparison.")

    story += term("clean_ocr_number()",
        "A helper function in table_extractor.py that fixes common OCR misreads in numeric fields. "
        "For example: OCR often reads '0' as 'O', '1' as 'l' or 'I', '5' as 'S', and inserts spaces inside multi-digit numbers. "
        "This function corrects all of these before the number is parsed as a float.")

    # ══════════════════════════════════════════════════════════════════════
    # PART 2 — EVALUATOR Q&A
    # ══════════════════════════════════════════════════════════════════════
    story += [PageBreak()]
    story += section("Part 2 — Likely Evaluator Questions &amp; Answers")

    story += qa(
        "What problem does your project solve?",
        "Businesses — especially in India — receive invoices in many different formats: digital PDFs, scanned PDFs, and photos. "
        "Manually typing the data from each invoice into an accounting system is slow and error-prone. "
        "My project automates this: you upload an invoice, and the system returns all key fields — vendor, amounts, line items, GST details — "
        "as structured, validated data, ready to go into any ERP or database."
    )

    story += qa(
        "Why did you use an LLM instead of just regex?",
        "Regex is great for fields that always look the same — a GSTIN is always 15 characters in a fixed format, so regex handles it perfectly. "
        "But fields like vendor name or billing address can appear anywhere on the invoice in any wording. "
        "An LLM can read the whole invoice text and figure out which part is the vendor name even if it is formatted unusually. "
        "We use both: regex for precision on structured fields, LLM for flexibility on free-text fields."
    )

    story += qa(
        "Why Ollama instead of the OpenAI or Gemini API?",
        "Three reasons: cost, privacy, and offline operation. "
        "Cloud APIs charge per token and require an internet connection. "
        "More importantly, invoices contain sensitive financial and business data — sending them to a third-party cloud API is a data privacy risk. "
        "Ollama runs entirely on the local machine, so no invoice data ever leaves the premises."
    )

    story += qa(
        "What is the accuracy of the system?",
        "For digital PDFs (pdfplumber extraction), all 14 header fields are extracted correctly on the invoices tested, with validation passing. "
        "For image invoices, header fields like vendor name, amounts, and GST details are correctly extracted, "
        "but line-item extraction on complex scanned tables still has OCR-related errors that are being worked on."
    )

    story += qa(
        "How does the validation work?",
        "After extraction, the validator runs five checks. First, it verifies the GSTIN format matches the 15-character Indian standard. "
        "Second, it checks that tax_amount equals subtotal times the tax rate, within a 0.5% tolerance. "
        "Third, it checks that total equals subtotal plus tax. "
        "Fourth, it checks that the sum of all line totals matches the subtotal — but it's smart enough to exclude shipping and freight charges, "
        "which are not part of the product subtotal. "
        "Fifth, it checks that the invoice date is not after the due date."
    )

    story += qa(
        "What is BM25 and why did you use it for search?",
        "BM25 is a classic text ranking algorithm — the same basic idea that early search engines used. "
        "It works by counting how often search terms appear in a document, weighted by how rare those terms are across all documents. "
        "I chose it because it requires no training, works offline, and handles searches like 'find all invoices from vendor XYZ' or 'show invoices with this GSTIN' very effectively. "
        "It also updates incrementally — each new invoice is added to the index immediately after extraction."
    )

    story += qa(
        "What are the limitations of the system?",
        "Three main ones. First, image OCR quality depends on the scan quality — very blurry or low-contrast invoices still produce noisy text. "
        "Second, PPStructure (a more powerful table parser) is not functional on Python 3.14 because the paddlepaddle backend has no wheel for that version; "
        "fixing this requires Python 3.12 or lower. "
        "Third, for invoices where line totals include GST (post-tax), the unit price back-calculation gives the correct math but the wrong semantic value — "
        "detecting pre-tax vs post-tax at the pipeline level is the planned fix."
    )

    story += qa(
        "Why did you choose qwen2.5:3b specifically?",
        "It was the best balance of speed and accuracy for the available hardware — a laptop with 8 GB RAM. "
        "I tested llama3 (8 billion parameters) but it consistently timed out at 120 seconds on full invoices. "
        "Phi3:mini was faster but less accurate on structured JSON extraction. "
        "qwen2.5:3b completes extraction in about 45 seconds with zero retries when format:json is enforced."
    )

    story += qa(
        "How does the dual-path extraction work for PDFs vs images?",
        "The system first detects the file type. If it is a digital PDF — meaning it was created by software and has a text layer — "
        "pdfplumber reads the text directly from the PDF structure. This is fast (under 1 second) and perfectly accurate. "
        "If it is an image or a scanned PDF — meaning it is essentially a photograph — "
        "the system converts it to a greyscale image, applies contrast enhancement and upscaling if needed, "
        "and then runs Tesseract OCR to convert the image into text."
    )

    story += qa(
        "What happens if the LLM returns a wrong value?",
        "The system has two safety nets. First, the regex backfill stage runs after the LLM and can override specific fields "
        "if the regex finds a more reliable match — for example, if the LLM returns the wrong currency but the invoice contains a GSTIN, "
        "the system forces the currency to INR because GSTIN is India-only. "
        "Second, the validation framework flags any result where the numbers do not add up, so a human reviewer knows which invoices to check."
    )

    story += qa(
        "How does the bill_to.name cleanup work?",
        "LLMs often return the entire billing address as one block of text in the name field. "
        "The system splits on newlines — the first line becomes the name, the rest moves to the address field. "
        "It also strips trailing 6-digit PIN codes from the name, and if the result is still over 80 characters (which means it is probably an address, not a name), it clears the field."
    )

    story += qa(
        "Could this be extended to support non-Indian invoices?",
        "Yes. The core pipeline — OCR, LLM extraction, regex backfill, validation — is format-agnostic. "
        "The India-specific parts are: GSTIN validation, CGST/SGST/IGST detection, and the INR currency forcing. "
        "These are isolated in the regex patterns and validator. "
        "Adding support for, say, EU VAT invoices would require updating the tax field patterns and replacing the GSTIN check with a VAT number check."
    )

    story += qa(
        "What would you do differently if starting again?",
        "I would use Python 3.11 or 3.12 from the start — the PPStructure table parser from PaddlePaddle requires it, "
        "and it would significantly improve table extraction on scanned invoices. "
        "I would also add a confidence threshold that routes low-confidence extractions to a human review queue, "
        "rather than passing them through validation and potentially failing there."
    )

    story += qa(
        "What is the difference between CGST/SGST and IGST?",
        "When a supplier and customer are in the same Indian state, GST is split 50-50 between the central government (CGST) "
        "and the state government (SGST). When they are in different states, the full GST goes to the central government as IGST. "
        "The total tax rate is the same either way — for example, 18% GST is either 9% CGST + 9% SGST, or 18% IGST. "
        "The system detects which type is on the invoice and maps both to the tax_amount field correctly."
    )

    doc.build(story)
    print(f"[✓] Q&A PDF saved: {path}")
    return path


if __name__ == "__main__":
    build_slide_pdf()
    build_qa_pdf()
    print("\nDone. Both PDFs are in:")
    print(f"  {OUTPUT_DIR}")
