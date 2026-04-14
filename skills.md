# RAG System Skills & Technical Competencies

**Project**: Invoice Extraction & Retrieval-Augmented Generation System  
**Last Updated**: April 2026  
**Purpose**: Document the technical skills and knowledge required to build, maintain, and enhance the RAG-powered invoice extraction system

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Core Technical Skills](#2-core-technical-skills)
3. [Python Development Skills](#3-python-development-skills)
4. [Machine Learning & NLP Skills](#4-machine-learning--nlp-skills)
5. [RAG System Implementation Skills](#5-rag-system-implementation-skills)
6. [Document Processing Skills](#6-document-processing-skills)
7. [Database & Data Engineering Skills](#7-database--data-engineering-skills)
8. [Web Development & API Skills](#8-web-development--api-skills)
9. [LLM & Prompt Engineering Skills](#9-llm--prompt-engineering-skills)
10. [DevOps & System Administration Skills](#10-devops--system-administration-skills)
11. [Domain Knowledge](#11-domain-knowledge)
12. [Evaluation & Testing Skills](#12-evaluation--testing-skills)

---

## 1. System Architecture Overview

### Current System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    INVOICE EXTRACTION SYSTEM                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │───▶│   FastAPI    │───▶│  Extraction  │  │
│  │  (Streamlit) │    │     API      │    │   Pipeline   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                             │                     │          │
│                             ▼                     ▼          │
│                      ┌──────────────┐    ┌──────────────┐  │
│                      │  RAG System  │    │  SQLite DB   │  │
│                      │              │    │              │  │
│                      │ • Router     │    │ • Invoices   │  │
│                      │ • SQL Search │    │ • Line Items │  │
│                      │ • BM25       │    │ • Validation │  │
│                      │ • Vector     │    └──────────────┘  │
│                      │ • Hybrid     │                      │
│                      └──────────────┘                      │
│                             │                               │
│                             ▼                               │
│                      ┌──────────────┐                      │
│                      │   ChromaDB   │                      │
│                      │  (Vectors)   │                      │
│                      └──────────────┘                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack Summary

| Category | Technologies |
|----------|-------------|
| **Core Language** | Python 3.10+ |
| **OCR Engines** | PaddleOCR (primary), Tesseract, EasyOCR |
| **PDF Processing** | pdfplumber, PyMuPDF, pdf2image |
| **LLM** | Ollama (qwen2.5:3b default) |
| **Vector DB** | ChromaDB 1.0.0+ |
| **Embeddings** | Sentence-Transformers (all-MiniLM-L6-v2) |
| **Keyword Search** | BM25Okapi, rank_bm25 |
| **Web Framework** | FastAPI 0.109.0+, Streamlit 1.30.0+ |
| **Database** | SQLAlchemy 2.0.0+, SQLite |
| **Computer Vision** | OpenCV, Pillow (PIL) |
| **Data Processing** | Pandas 2.0.0+, NumPy |

---

## 2. Core Technical Skills

### Programming Languages

#### Python (Primary Language)
- **Required Proficiency**: Advanced
- **Version**: Python 3.10+
- **Key Areas**:
  - Object-oriented programming
  - Async/await patterns
  - Type hints and Pydantic models
  - Context managers and decorators
  - Error handling and exception hierarchies
  - List comprehensions and generators
  - Lambda functions and functional programming

**Example Skills**:
```python
# Async programming for API endpoints
async def process_batch(files: List[UploadFile]) -> Dict[str, Any]:
    results = await asyncio.gather(*[extract_invoice(f) for f in files])
    
# Type-safe data models with Pydantic
class InvoiceSchema(BaseModel):
    invoice_number: Optional[str] = None
    total_amount: Optional[float] = Field(None, ge=0)
    
# Context managers for resource cleanup
with database_session() as session:
    invoice = session.query(Invoice).filter_by(id=invoice_id).first()
```

### Software Development Practices

- **Version Control**: Git, GitHub workflows
- **Code Organization**: Modular architecture, separation of concerns
- **Documentation**: Docstrings, type hints, README files
- **Testing**: Unit tests, integration tests, regression tests
- **Debugging**: Logging, error tracing, performance profiling
- **Code Quality**: PEP 8 compliance, linting, code reviews

---

## 3. Python Development Skills

### Package Management

- **pip**: Installing and managing dependencies
- **requirements.txt**: Version pinning and constraint files
- **Virtual Environments**: venv, conda
- **Dependency Resolution**: Handling version conflicts

**Required Packages** (46+ total):
```txt
# Core
python-dotenv>=1.0.0
PyYAML>=6.0.1

# Image & PDF
Pillow>=10.0.0
opencv-python-headless>=4.8.0
pdf2image>=1.16.3
PyMuPDF>=1.23.0
pdfplumber>=0.10.0

# OCR
pytesseract>=0.3.10
easyocr>=1.7.0
paddleocr>=2.7.0

# LLM & RAG
ollama>=0.4.0
chromadb>=1.0.0
sentence-transformers>=3.0.0
rank_bm25>=0.2.2

# Web
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
streamlit>=1.30.0

# Data & ORM
SQLAlchemy>=2.0.0
pandas>=2.0.0
openpyxl>=3.1.0
```

### Pydantic Data Validation

- **Schema Definition**: Creating data models with validation
- **Type Coercion**: Automatic type conversion
- **Custom Validators**: Field-level and model-level validation
- **JSON Serialization**: Model export and import

**Key Models in Project**:
```python
class VendorInfo(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None

class LineItemSchema(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = Field(None, ge=0)
    unit_price: Optional[float] = Field(None, ge=0)
    discount: Optional[float] = Field(0, ge=0)
    tax_rate: Optional[float] = Field(None, ge=0, le=100)
    total: Optional[float] = None

class InvoiceSchema(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    vendor: Optional[VendorInfo] = None
    bill_to: Optional[BillToInfo] = None
    line_items: List[LineItemSchema] = []
    total_amount: Optional[float] = None
    metadata: Optional[ExtractionMetadata] = None
```

### Environment Management

- **python-dotenv**: Loading configuration from `.env` files
- **Configuration Classes**: Centralized config management
- **Environment Variables**: Security best practices

**Configuration Skills** (`core/config.py`):
```python
from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    OCR_ENGINE = os.getenv("OCR_ENGINE", "paddleocr")
    LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/invoices.db")
```

---

## 4. Machine Learning & NLP Skills

### Vector Embeddings

#### Sentence-Transformers
- **Model Selection**: Choosing appropriate embedding models
- **Embedding Generation**: Converting text to dense vectors
- **Dimensionality**: Understanding vector sizes (384-dim for all-MiniLM-L6-v2)
- **Semantic Similarity**: Cosine similarity calculations

**Key Skills**:
```python
from sentence_transformers import SentenceTransformer

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Generate embeddings
texts = ["Invoice from Acme Corp", "Bill from Acme Corporation"]
embeddings = model.encode(texts)  # Shape: (2, 384)

# Calculate similarity
from sklearn.metrics.pairwise import cosine_similarity
similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
```

### Keyword Search Algorithms

#### BM25 (Best Matching 25)
- **Algorithm Understanding**: TF-IDF variant with length normalization
- **Index Building**: Creating and persisting BM25 indexes
- **Tokenization**: Porter stemming, stopword removal
- **Parameter Tuning**: k1 (term saturation) and b (length normalization)

**Implementation** (`rag/bm25_retriever.py`):
```python
from rank_bm25 import BM25Okapi

class BM25Retriever:
    def __init__(self, documents: List[str]):
        # Tokenize documents
        self.tokenized_corpus = [self._tokenize(doc) for doc in documents]
        # Build BM25 index
        self.bm25 = BM25Okapi(self.tokenized_corpus)
    
    def search(self, query: str, top_k: int = 5) -> List[int]:
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return top_indices.tolist()
```

### Query Expansion Techniques

#### HyDE (Hypothetical Document Embeddings)
- **Concept**: Generate synthetic documents from queries
- **Implementation**: LLM-based query expansion
- **Use Case**: Improving vector search recall

**HyDE Process**:
```python
def expand_query_with_hyde(query: str, llm_client) -> str:
    """Generate hypothetical document from query."""
    prompt = f"""Given this question about invoices:
    {query}
    
    Generate a hypothetical invoice excerpt that would answer this question:"""
    
    synthetic_doc = llm_client.generate(prompt)
    expanded_query = query + " " + synthetic_doc
    return expanded_query
```

### Re-ranking Algorithms

#### Cross-Encoder Models
- **Architecture**: BERT-based bi-encoder scoring
- **Ranking**: Semantic relevance scoring
- **Top-K Selection**: Re-ranking retrieved candidates

**Re-ranking Implementation** (`rag/reranker.py`):
```python
from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        self.cross_encoder = CrossEncoder(model_name)
    
    def rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        # Score all query-document pairs
        pairs = [(query, doc) for doc in documents]
        scores = self.cross_encoder.predict(pairs)
        
        # Sort by score descending
        ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
```

### Reciprocal Rank Fusion (RRF)

**Hybrid Ranking Formula**:
```python
def reciprocal_rank_fusion(
    rankings: List[List[str]], 
    k: int = 60
) -> List[str]:
    """Merge multiple ranking lists using RRF."""
    rrf_scores = {}
    
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0
            rrf_scores[doc_id] += 1 / (k + rank)
    
    # Sort by RRF score descending
    merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, score in merged]
```

---

## 5. RAG System Implementation Skills

### Query Understanding & Routing

#### Intent Detection
- **Pattern Matching**: Regex and keyword-based routing
- **Strategy Selection**: SQL vs BM25 vs Vector vs Hybrid
- **Filter Extraction**: Parsing date ranges, amounts, vendor names

**Router Implementation** (`rag/router.py`):
```python
class QueryRouter:
    def route(self, question: str) -> str:
        """Determine optimal retrieval strategy."""
        question_lower = question.lower()
        
        # SQL strategy triggers
        if any(kw in question_lower for kw in [
            "how many", "total", "sum", "average", "count", "highest", "lowest"
        ]):
            return "sql"
        
        # BM25 strategy triggers (exact matches)
        if re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b', question):  # GSTIN
            return "bm25"
        if re.search(r'invoice\s*#?\s*\d+', question_lower):
            return "bm25"
        
        # Vector strategy triggers
        if any(kw in question_lower for kw in [
            "similar", "related", "describe", "category", "like", "about"
        ]):
            return "vector"
        
        # Default to hybrid
        return "hybrid"
```

### Multi-Strategy Retrieval

#### SQL Retrieval
- **Natural Language to SQL**: LLM-based query translation
- **SQLAlchemy Query Building**: Programmatic SQL generation
- **Aggregation Queries**: SUM, COUNT, AVG, GROUP BY

**SQL Retrieval Example** (`rag/sql_retriever.py`):
```python
def retrieve_with_sql(question: str, llm_client, db_session) -> Dict[str, Any]:
    """Translate question to SQL and execute."""
    # Generate SQL from natural language
    prompt = f"""Translate this question to SQL:
    {question}
    
    Available tables:
    - invoices (invoice_number, invoice_date, vendor_name, total_amount, ...)
    - line_items (invoice_id, description, quantity, unit_price, total, ...)
    
    Return ONLY the SQL query, no explanation:"""
    
    sql_query = llm_client.generate(prompt)
    
    # Execute query
    result = db_session.execute(text(sql_query))
    rows = result.fetchall()
    
    return {
        "strategy": "sql",
        "sql_query": sql_query,
        "results": [dict(row) for row in rows]
    }
```

#### BM25 Keyword Retrieval
- **Tokenization**: Text preprocessing
- **Index Persistence**: Pickle serialization
- **Scoring**: BM25 relevance scoring

#### Vector Semantic Retrieval
- **ChromaDB Integration**: Persistent vector store
- **Embedding Function**: Sentence-Transformers wrapper
- **Similarity Search**: Cosine similarity queries

**Vector Retrieval** (`rag/indexer.py`):
```python
import chromadb
from chromadb.utils import embedding_functions

class VectorRetriever:
    def __init__(self, persist_dir: str = "chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="invoices",
            embedding_function=self.embedding_fn
        )
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        return results
```

#### Hybrid Retrieval
- **Multi-Source Results**: Combine BM25 + Vector
- **Rank Fusion**: Reciprocal Rank Fusion algorithm
- **Deduplication**: Remove duplicate results

### Chunking Strategies

#### Invoice-Specific Chunking
- **Header Chunks**: Invoice metadata (dates, numbers, totals)
- **Line Item Chunks**: Individual itemized charges
- **Source Attribution**: Track origin of each chunk

**Chunking Implementation** (`rag/chunker.py`):
```python
def chunk_invoice(invoice_data: Dict) -> List[Dict]:
    """Split invoice into searchable chunks."""
    chunks = []
    
    # Chunk 1: Header information
    header_text = f"""
    Invoice Number: {invoice_data.get('invoice_number')}
    Date: {invoice_data.get('invoice_date')}
    Vendor: {invoice_data.get('vendor', {}).get('name')}
    Total: {invoice_data.get('total_amount')}
    """
    chunks.append({
        "text": header_text,
        "type": "header",
        "source": invoice_data.get('source_file'),
        "invoice_id": invoice_data.get('invoice_number')
    })
    
    # Chunk 2-N: Line items
    for idx, item in enumerate(invoice_data.get('line_items', [])):
        item_text = f"""
        Item: {item.get('description')}
        Quantity: {item.get('quantity')}
        Unit Price: {item.get('unit_price')}
        Total: {item.get('total')}
        """
        chunks.append({
            "text": item_text,
            "type": "line_item",
            "source": invoice_data.get('source_file'),
            "invoice_id": invoice_data.get('invoice_number'),
            "line_number": idx + 1
        })
    
    return chunks
```

### Conversation Memory

#### Context Management
- **Turn-Based Storage**: Keep last N conversation turns
- **Context Injection**: Add history to LLM prompts
- **Reference Resolution**: Handle follow-up questions

**Memory Implementation** (`rag/qa_chain.py`):
```python
class ConversationMemory:
    def __init__(self, max_turns: int = 5):
        self.max_turns = max_turns
        self.history: List[Dict[str, str]] = []
    
    def add_turn(self, question: str, answer: str):
        self.history.append({"question": question, "answer": answer})
        # Keep only last N turns
        if len(self.history) > self.max_turns:
            self.history = self.history[-self.max_turns:]
    
    def format_context(self) -> str:
        """Format conversation history for LLM."""
        if not self.history:
            return ""
        
        context = "Previous conversation:\n"
        for turn in self.history:
            context += f"Q: {turn['question']}\nA: {turn['answer']}\n\n"
        return context
```

### QA Chain Architecture

**End-to-End Question Answering Flow**:
```python
class QAChain:
    def __init__(self, router, retrievers, llm_client, memory):
        self.router = router
        self.retrievers = retrievers
        self.llm = llm_client
        self.memory = memory
    
    def answer(self, question: str) -> Dict[str, Any]:
        # 1. Route to strategy
        strategy = self.router.route(question)
        
        # 2. Retrieve relevant context
        if strategy == "sql":
            context = self.retrievers["sql"].retrieve(question)
        elif strategy == "bm25":
            context = self.retrievers["bm25"].search(question)
        elif strategy == "vector":
            context = self.retrievers["vector"].search(question)
        else:  # hybrid
            bm25_results = self.retrievers["bm25"].search(question)
            vector_results = self.retrievers["vector"].search(question)
            context = self.merge_results(bm25_results, vector_results)
        
        # 3. Build prompt with context
        history = self.memory.format_context()
        prompt = self._build_prompt(question, context, history)
        
        # 4. Generate answer
        answer = self.llm.generate(prompt)
        
        # 5. Store in memory
        self.memory.add_turn(question, answer)
        
        return {
            "answer": answer,
            "strategy": strategy,
            "sources": self._extract_sources(context),
            "context": context
        }
```

---

## 6. Document Processing Skills

### OCR (Optical Character Recognition)

#### PaddleOCR
- **Model Architecture**: PP-OCRv4 (detection + recognition)
- **Language Support**: Multi-language OCR
- **GPU Acceleration**: CUDA support for faster inference
- **Confidence Scoring**: Per-word confidence metrics

**PaddleOCR Usage** (`core/ocr_engine.py`):
```python
from paddleocr import PaddleOCR

class OCREngine:
    def __init__(self):
        self.paddle_ocr = PaddleOCR(
            use_angle_cls=True,  # Enable angle detection
            lang='en',
            use_gpu=False,
            show_log=False
        )
    
    def run_ocr(self, image_path: str) -> str:
        result = self.paddle_ocr.ocr(image_path, cls=True)
        
        # Extract text from bounding boxes
        text_lines = []
        for line in result[0]:
            bbox, (text, confidence) = line
            text_lines.append(text)
        
        return "\n".join(text_lines)
```

#### Tesseract OCR
- **Installation**: pytesseract wrapper
- **Language Data**: Trained data files
- **PSM Modes**: Page segmentation modes
- **Configuration**: Custom Tesseract configs

#### EasyOCR
- **Framework**: PyTorch-based OCR
- **Multi-language**: 80+ languages
- **Logo Extraction**: Vendor name from logos

### Image Preprocessing

#### PIL (Pillow) Techniques
- **Grayscale Conversion**: RGB to grayscale
- **Contrast Enhancement**: Improve text visibility
- **Binarization**: Thresholding for black/white
- **Denoising**: Gaussian blur

**Preprocessing Pipeline** (`core/ocr_engine.py`):
```python
from PIL import Image, ImageEnhance, ImageFilter

def preprocess_image(image_path: str) -> Image.Image:
    """Enhance image quality for better OCR."""
    img = Image.open(image_path)
    
    # Convert to grayscale
    img = img.convert('L')
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    
    # Denoise with Gaussian blur
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    
    # Binarize (optional)
    # threshold = 128
    # img = img.point(lambda x: 0 if x < threshold else 255, '1')
    
    return img
```

#### OpenCV Processing
- **Image Resizing**: Scale for better recognition
- **Rotation Correction**: Deskewing
- **Adaptive Thresholding**: Local binarization
- **Morphological Operations**: Erosion, dilation

### PDF Processing

#### pdfplumber
- **Text Extraction**: Layout-aware text extraction
- **Table Detection**: Extract tables from PDFs
- **Metadata Parsing**: PDF properties
- **Page-Level Processing**: Per-page extraction

**pdfplumber Usage** (`core/pdf_extractor.py`):
```python
import pdfplumber

def extract_digital_pdf(pdf_path: str) -> str:
    """Extract text from searchable PDFs."""
    text_content = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)
    
    return "\n".join(text_content)
```

#### PyMuPDF (fitz)
- **Fast Rendering**: High-performance PDF parsing
- **Image Extraction**: Extract embedded images
- **Text Search**: Find keywords in PDFs
- **Annotation Support**: Read PDF annotations

#### pdf2image
- **PDF to Image**: Convert PDF pages to images
- **DPI Control**: Resolution settings (default 300 DPI)
- **Multi-Page Handling**: Batch conversion

### Table Extraction

#### Multi-Engine Strategy
- **pdfplumber**: Grid-based detection
- **Camelot**: Bordered table extraction
- **Tabula**: Stream and lattice modes
- **Regex Fallback**: Pattern-based extraction

**Table Extraction** (`core/table_extractor.py`):
```python
import pdfplumber

def extract_tables(pdf_path: str) -> List[List[List[str]]]:
    """Extract tables from PDF using multiple engines."""
    tables = []
    
    # Try pdfplumber first
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    
    # If no tables found, try Camelot (bordered tables)
    if not tables:
        try:
            import camelot
            camelot_tables = camelot.read_pdf(pdf_path, flavor='lattice')
            tables = [table.df.values.tolist() for table in camelot_tables]
        except:
            pass
    
    return tables
```

### File Type Detection

**Detection Logic** (`core/detector.py`):
```python
def detect_file_type(file_path: str) -> str:
    """Classify as digital PDF, scanned PDF, or image."""
    if file_path.lower().endswith('.pdf'):
        # Check if PDF has extractable text
        with pdfplumber.open(file_path) as pdf:
            first_page_text = pdf.pages[0].extract_text() or ""
            
            if len(first_page_text) > 50:  # Threshold
                return "digital"
            else:
                return "scanned"
    else:
        return "image"
```

---

## 7. Database & Data Engineering Skills

### SQLAlchemy ORM

#### Schema Definition
- **Declarative Base**: Table class definitions
- **Relationships**: Foreign keys, one-to-many, many-to-one
- **Column Types**: String, Integer, Float, DateTime, JSON
- **Constraints**: Primary keys, unique constraints, indexes

**Database Schema** (`core/db.py`):
```python
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Invoice(Base):
    __tablename__ = 'invoices'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_number = Column(String, unique=True, index=True)
    invoice_date = Column(String)
    vendor_name = Column(String, index=True)
    total_amount = Column(Float)
    source_file = Column(String)
    created_at = Column(DateTime)
    
    # Relationships
    line_items = relationship("LineItem", back_populates="invoice")
    validation = relationship("ValidationReport", back_populates="invoice", uselist=False)

class LineItem(Base):
    __tablename__ = 'line_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'))
    description = Column(String)
    quantity = Column(Float)
    unit_price = Column(Float)
    total = Column(Float)
    
    invoice = relationship("Invoice", back_populates="line_items")

class ValidationReport(Base):
    __tablename__ = 'validation_reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'))
    passed = Column(Integer)  # Boolean as int
    warnings = Column(String)  # JSON string
    
    invoice = relationship("Invoice", back_populates="validation")
```

#### Query Building
- **Session Management**: Context managers for transactions
- **Filtering**: WHERE clauses with SQLAlchemy syntax
- **Joins**: Cross-table queries
- **Aggregations**: COUNT, SUM, AVG, GROUP BY

**Query Examples**:
```python
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

# Create session
Session = sessionmaker(bind=engine)

with Session() as session:
    # Simple filter
    invoices = session.query(Invoice).filter(
        Invoice.vendor_name == "Acme Corp"
    ).all()
    
    # Aggregation
    total_by_vendor = session.query(
        Invoice.vendor_name,
        func.sum(Invoice.total_amount).label('total')
    ).group_by(Invoice.vendor_name).all()
    
    # Join with line items
    invoices_with_items = session.query(Invoice).join(
        LineItem
    ).filter(
        LineItem.description.like('%laptop%')
    ).all()
```

### SQLite Operations

#### Database Initialization
- **Schema Creation**: CREATE TABLE statements
- **Index Creation**: Performance optimization
- **Data Migration**: Schema updates

#### Transaction Management
- **ACID Properties**: Atomicity, Consistency, Isolation, Durability
- **Rollback Handling**: Error recovery
- **Batch Inserts**: Bulk data loading

### Data Serialization

#### JSON Handling
- **python json module**: Parsing and serialization
- **Pretty Printing**: Human-readable output
- **Custom Encoders**: Handle datetime, Decimal types

**JSON Export**:
```python
import json
from datetime import datetime
from decimal import Decimal

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def save_extraction(data: Dict, output_path: str):
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, cls=CustomEncoder, ensure_ascii=False)
```

#### Excel Export
- **openpyxl**: Writing Excel files
- **Multi-Sheet Workbooks**: Separate sheets for header and line items
- **Formatting**: Column widths, number formats

**Excel Export** (`frontend/ui_helpers.py`):
```python
import openpyxl
from openpyxl.styles import Font, Alignment

def export_to_excel(invoice_data: Dict, output_path: str):
    wb = openpyxl.Workbook()
    
    # Sheet 1: Header
    ws_header = wb.active
    ws_header.title = "Invoice Header"
    ws_header.append(["Field", "Value"])
    ws_header.append(["Invoice Number", invoice_data.get('invoice_number')])
    ws_header.append(["Total Amount", invoice_data.get('total_amount')])
    
    # Sheet 2: Line Items
    ws_items = wb.create_sheet("Line Items")
    ws_items.append(["Description", "Quantity", "Unit Price", "Total"])
    for item in invoice_data.get('line_items', []):
        ws_items.append([
            item.get('description'),
            item.get('quantity'),
            item.get('unit_price'),
            item.get('total')
        ])
    
    wb.save(output_path)
```

### Pandas Data Processing

- **DataFrame Operations**: Filter, group, aggregate
- **CSV/Excel Reading**: Load structured data
- **Data Cleaning**: Handle missing values, type conversion
- **Pivot Tables**: Data reshaping

---

## 8. Web Development & API Skills

### FastAPI Framework

#### Async Endpoints
- **async/await**: Asynchronous request handling
- **Background Tasks**: Non-blocking operations
- **Dependency Injection**: Shared resources

**API Endpoints** (`api/main.py`):
```python
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from typing import List

app = FastAPI(title="Invoice Extraction API", version="2.0.0")

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}

@app.post("/extract")
async def extract_invoice(file: UploadFile = File(...)):
    """Extract structured data from invoice."""
    if not file.filename.endswith(('.pdf', '.png', '.jpg', '.jpeg')):
        raise HTTPException(400, "Unsupported file type")
    
    # Save uploaded file
    temp_path = f"temp/{file.filename}"
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Process invoice
    result = pipeline.process_invoice(temp_path)
    
    return JSONResponse(content={
        "status": "success",
        "data": result
    })

@app.post("/ask")
async def ask_question(request: dict):
    """Answer questions using RAG."""
    question = request.get("question")
    if not question:
        raise HTTPException(400, "Question is required")
    
    answer = qa_chain.answer(question)
    return answer
```

#### Request/Response Models
- **Pydantic Validation**: Request body validation
- **Response Models**: Type-safe responses
- **Status Codes**: HTTP status code management

#### File Upload Handling
- **Multipart Form Data**: Handle file uploads
- **Temporary File Storage**: Secure temp file management
- **Cleanup**: Remove temporary files after processing

#### CORS Configuration
- **Cross-Origin Requests**: Allow frontend access
- **Allowed Origins**: Security configuration
- **Credentials**: Cookie/auth header handling

**CORS Setup**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Streamlit Frontend

#### UI Components
- **File Uploader**: `st.file_uploader()`
- **Text Input**: `st.text_input()`, `st.text_area()`
- **Buttons**: `st.button()`, `st.download_button()`
- **Tabs**: `st.tabs()`
- **Columns**: `st.columns()`
- **Metrics**: `st.metric()`

**Streamlit App** (`frontend/app.py`):
```python
import streamlit as st

st.set_page_config(page_title="Invoice Extraction", layout="wide")

# Tabs
tab1, tab2, tab3 = st.tabs(["Extract Invoice", "Ask a Question", "RAG Dashboard"])

with tab1:
    st.header("📄 Invoice Extraction")
    
    uploaded_file = st.file_uploader(
        "Upload Invoice (PDF or Image)",
        type=['pdf', 'png', 'jpg', 'jpeg']
    )
    
    if uploaded_file:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Document Preview")
            # Display document
            if uploaded_file.type == "application/pdf":
                st.image(convert_pdf_to_image(uploaded_file))
            else:
                st.image(uploaded_file)
        
        with col2:
            st.subheader("Extraction Results")
            # Process and display results
            result = process_invoice(uploaded_file)
            st.json(result)
```

#### Session State Management
- **st.session_state**: Persist data across reruns
- **Caching**: `@st.cache_data`, `@st.cache_resource`
- **Widget State**: Maintain form inputs

#### Data Visualization
- **Plotly Charts**: Interactive visualizations
- **Tables**: `st.dataframe()`, `st.table()`
- **Metrics Display**: KPI cards

**Plotly Waterfall Chart** (`frontend/ui_helpers.py`):
```python
import plotly.graph_objects as go

def render_financial_waterfall(invoice_data: Dict):
    """Display financial breakdown as waterfall chart."""
    subtotal = invoice_data.get('subtotal', 0)
    tax = invoice_data.get('tax_amount', 0)
    discount = invoice_data.get('discount', 0)
    total = invoice_data.get('total_amount', 0)
    
    fig = go.Figure(go.Waterfall(
        x=["Subtotal", "Tax", "Discount", "Total"],
        y=[subtotal, tax, -discount, total],
        measure=["absolute", "relative", "relative", "total"]
    ))
    
    st.plotly_chart(fig, use_container_width=True)
```

### API Testing

- **Requests Library**: Making HTTP calls
- **Status Code Validation**: Ensure correct responses
- **Error Handling**: Handle API errors gracefully

---

## 9. LLM & Prompt Engineering Skills

### Ollama Integration

#### Model Management
- **Model Selection**: Choose appropriate models (qwen2.5:3b, llama3, etc.)
- **Model Loading**: Pull and cache models locally
- **API Communication**: HTTP requests to Ollama server

**Ollama Client** (`core/llm_extractor.py`):
```python
import requests
import json

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen2.5:3b"):
        self.base_url = base_url
        self.model = model
        self.timeout = 120
    
    def generate(self, prompt: str, temperature: float = 0) -> str:
        """Generate text completion from prompt."""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        
        return response.json()['response']
```

### Prompt Engineering

#### Structured Extraction Prompts
- **System Instructions**: Define assistant behavior
- **Task Description**: Clear extraction requirements
- **Output Format**: JSON schema specification
- **Examples**: Few-shot learning

**Invoice Extraction Prompt**:
```python
def build_extraction_prompt(ocr_text: str) -> str:
    return f"""You are an invoice data extraction assistant. Extract the following fields from the invoice text and return them in JSON format.

Required fields:
- invoice_number: string
- invoice_date: string (YYYY-MM-DD format)
- vendor_name: string
- vendor_address: string
- vendor_gstin: string (15-character Indian GST number)
- total_amount: float
- line_items: array of objects with description, quantity, unit_price, total

Invoice text:
{ocr_text}

Return ONLY valid JSON, no additional text:"""
```

#### Query Translation Prompts
- **Natural Language to SQL**: Convert questions to SQL
- **Contextual Instructions**: Guide LLM behavior
- **Constraints**: Specify allowed operations

**SQL Translation Prompt**:
```python
def build_sql_prompt(question: str) -> str:
    return f"""Translate the following question into a SQL query.

Available tables and columns:
- invoices: id, invoice_number, invoice_date, vendor_name, total_amount, created_at
- line_items: id, invoice_id, description, quantity, unit_price, total

Question: {question}

Return ONLY the SQL query, no explanation or markdown:"""
```

#### QA Generation Prompts
- **Context Injection**: Provide relevant information
- **Grounding Instructions**: Prevent hallucinations
- **Source Attribution**: Request citations

**RAG QA Prompt**:
```python
def build_qa_prompt(question: str, context: str, history: str = "") -> str:
    return f"""You are an invoice analysis assistant. Answer the question based ONLY on the provided context.

Rules:
1. If the context doesn't contain enough information, say "I don't have enough information to answer that."
2. Always cite the invoice number and source file for your answers.
3. For numerical answers, show your calculations.
4. Use currency symbols (₹, $) appropriately.

{history}

Context:
{context}

Question: {question}

Answer:"""
```

### JSON Parsing & Fallbacks

#### Robust JSON Extraction
- **json.loads()**: Parse JSON strings
- **Error Handling**: Handle malformed JSON
- **Regex Fallback**: Extract fields when JSON fails

**JSON Extraction with Fallback**:
```python
import json
import re

def extract_json_or_fallback(llm_response: str) -> Dict:
    """Parse JSON from LLM, fallback to regex if needed."""
    try:
        # Try direct JSON parsing
        return json.loads(llm_response)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Fallback to regex field extraction
        return {
            "invoice_number": re.search(r'Invoice\s*#?:?\s*(\S+)', llm_response, re.I).group(1) if re.search(r'Invoice\s*#?:?\s*(\S+)', llm_response, re.I) else None,
            "total_amount": float(re.search(r'Total:?\s*₹?(\d+\.?\d*)', llm_response).group(1)) if re.search(r'Total:?\s*₹?(\d+\.?\d*)', llm_response) else None,
        }
```

### Hallucination Mitigation

- **Grounding**: Force LLM to use only provided context
- **Confidence Scores**: Request confidence levels
- **Verification**: Cross-check LLM outputs with rules
- **Temperature Control**: Use low temperature (0-0.2) for factual tasks

---

## 10. DevOps & System Administration Skills

### Environment Setup

#### Virtual Environments
- **venv**: Python virtual environment management
- **Activation**: Windows (Scripts\activate) vs Unix (bin/activate)
- **Dependency Installation**: `pip install -r requirements.txt`

#### System Dependencies
- **Tesseract OCR**: System-level installation
- **Poppler**: PDF rendering (for pdf2image)
- **OpenCV Dependencies**: System libraries

### Logging & Monitoring

#### Python logging Module
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Handlers**: File, console, rotating file handlers
- **Formatters**: Timestamp, log level, message

**Logging Configuration**:
```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger("invoice_extraction")
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        "logs/extraction.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
```

### Docker (Optional)

- **Dockerfile**: Container image definition
- **docker-compose**: Multi-container orchestration
- **Volume Mounts**: Persist data outside containers
- **Port Mapping**: Expose services

### Git Workflow

- **Branching**: Feature branches, main/develop
- **Commit Messages**: Conventional commits
- **Pull Requests**: Code review process
- **Merge Strategies**: Rebase, merge, squash

---

## 11. Domain Knowledge

### Invoice Structure

#### Header Information
- **Invoice Number**: Unique identifier
- **Invoice Date**: Issue date
- **Due Date**: Payment deadline
- **Purchase Order (PO)**: Reference number

#### Parties
- **Vendor/Seller**: Issuing party
  - Name, address, tax ID (GSTIN)
  - Contact: email, phone
- **Bill-To/Buyer**: Receiving party
  - Name, address, tax ID
  - Shipping address (if different)

#### Line Items
- **Description**: Product/service name
- **Quantity**: Number of units
- **Unit Price**: Price per unit
- **Discount**: Item-level or invoice-level
- **Tax Rate**: GST, VAT, sales tax percentage
- **Total**: Calculated amount per line

#### Financial Totals
- **Subtotal**: Sum of all line items before tax
- **Tax Amount**: Calculated tax (subtotal × tax_rate)
- **Discount**: Total discount applied
- **Grand Total**: Final payable amount

### GST (Goods and Services Tax)

#### GSTIN Format
- **Structure**: 15 characters
  - 2 digits: State code
  - 10 digits: PAN number
  - 1 digit: Entity number
  - 1 letter: 'Z' (default)
  - 1 digit: Checksum

**GSTIN Validation**:
```python
import re

def validate_gstin(gstin: str) -> bool:
    """Validate Indian GSTIN format."""
    if not gstin or len(gstin) != 15:
        return False
    
    # Pattern: 2 digits + 10 alphanumeric (PAN) + 1 digit + Z + 1 alphanumeric
    pattern = r'^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]$'
    return bool(re.match(pattern, gstin))
```

### Accounting Concepts

- **Debit vs Credit**: Double-entry bookkeeping
- **Accounts Payable**: Money owed to vendors
- **Accounts Receivable**: Money owed by customers
- **Purchase Order**: Pre-authorization for purchase
- **Proforma Invoice**: Preliminary bill before shipment

### Data Validation

#### Mathematical Validation
- **Line Item Sum**: Quantity × Unit Price = Line Total
- **Subtotal Check**: Sum of line items = Subtotal
- **Tax Calculation**: Subtotal × Tax Rate ≈ Tax Amount
- **Grand Total**: Subtotal + Tax - Discount = Total

**Validation Implementation** (`core/validator.py`):
```python
def validate_invoice(invoice_data: Dict) -> Dict[str, Any]:
    """Validate invoice data integrity."""
    warnings = []
    
    # Check line item math
    for idx, item in enumerate(invoice_data.get('line_items', [])):
        expected_total = item.get('quantity', 0) * item.get('unit_price', 0)
        actual_total = item.get('total', 0)
        
        if abs(expected_total - actual_total) > 0.01:
            warnings.append(f"Line {idx+1}: Math mismatch ({expected_total} vs {actual_total})")
    
    # Check subtotal
    calculated_subtotal = sum(item.get('total', 0) for item in invoice_data.get('line_items', []))
    stated_subtotal = invoice_data.get('subtotal', 0)
    
    if abs(calculated_subtotal - stated_subtotal) > 0.01:
        warnings.append(f"Subtotal mismatch ({calculated_subtotal} vs {stated_subtotal})")
    
    # Check grand total
    expected_total = stated_subtotal + invoice_data.get('tax_amount', 0) - invoice_data.get('discount', 0)
    actual_total = invoice_data.get('total_amount', 0)
    
    if abs(expected_total - actual_total) > 0.01:
        warnings.append(f"Total mismatch ({expected_total} vs {actual_total})")
    
    return {
        "passed": len(warnings) == 0,
        "warnings": warnings
    }
```

#### Date Format Normalization
- **Input Formats**: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD MMM YYYY
- **Output Format**: ISO 8601 (YYYY-MM-DD)
- **Parsing**: dateutil.parser, strptime

**Date Normalization**:
```python
from dateutil import parser
from datetime import datetime

def normalize_date(date_str: str) -> str:
    """Convert various date formats to YYYY-MM-DD."""
    try:
        dt = parser.parse(date_str, dayfirst=True)
        return dt.strftime('%Y-%m-%d')
    except:
        return date_str  # Return original if parsing fails
```

---

## 12. Evaluation & Testing Skills

### RAG Evaluation Metrics

#### Hit@K (Recall at K)
- **Definition**: Did the correct document appear in top K results?
- **Formula**: (Number of queries with correct doc in top K) / (Total queries)
- **Use Case**: Measure retrieval recall

**Hit@K Implementation** (`rag/evaluator.py`):
```python
def hit_at_k(retrieved_docs: List[str], ground_truth_docs: List[str], k: int = 5) -> float:
    """Calculate if any ground truth doc appears in top K results."""
    top_k = retrieved_docs[:k]
    return float(any(doc in top_k for doc in ground_truth_docs))
```

#### Mean Reciprocal Rank (MRR)
- **Definition**: Average of reciprocal ranks of first correct result
- **Formula**: MRR = (1/N) × Σ(1/rank_i)
- **Use Case**: Measure ranking quality

**MRR Implementation**:
```python
def mean_reciprocal_rank(retrieved_docs: List[str], ground_truth_docs: List[str]) -> float:
    """Calculate MRR for retrieval results."""
    for rank, doc in enumerate(retrieved_docs, start=1):
        if doc in ground_truth_docs:
            return 1.0 / rank
    return 0.0
```

#### Exact Match Accuracy
- **Definition**: Percentage of perfect answer matches
- **Normalization**: Lowercase, whitespace trimming
- **Use Case**: Factual Q&A evaluation

#### F1 Score (Token Overlap)
- **Precision**: Correct tokens / Total predicted tokens
- **Recall**: Correct tokens / Total ground truth tokens
- **F1**: Harmonic mean of precision and recall

### Ground Truth Creation

- **Manual Labeling**: Human-annotated answers
- **JSON Format**: Structured test cases
- **Coverage**: Representative sample of question types

**Ground Truth Format** (`data/ground_truth.json`):
```json
{
  "test_cases": [
    {
      "question": "What is the total amount for invoice INV-001?",
      "expected_answer": "₹15,240.00",
      "relevant_documents": ["invoice_001.json"],
      "answer_type": "exact_match"
    },
    {
      "question": "How many invoices are from Acme Corp?",
      "expected_answer": "12",
      "relevant_documents": ["invoice_001.json", "invoice_045.json", "..."],
      "answer_type": "numerical"
    }
  ]
}
```

### Regression Testing

- **Baseline Establishment**: Initial performance metrics
- **Change Detection**: Identify degradation
- **Automated Runs**: CI/CD integration
- **Reporting**: Metric comparison tables

---

## 13. Production-Ready Enhancements (April 2026)

This section documents the critical enhancements made to make the RAG system production-ready for everyday company use.

### Yes/No Query Handling

**Problem**: System was saying "I don't have enough information" for existence queries instead of answering "No".

**Solution**: Enhanced system prompt with explicit Yes/No logic:

```python
_SYSTEM_PROMPT = """
FOR YES/NO QUESTIONS ("Do we have...", "Is there...", "Are there any..."):
- If found in context: Answer "Yes" with specific details
- If NOT found in context: Answer "No, [item] was not found in the system."
- NEVER say "I don't have enough information" for existence queries
"""
```

### Dynamic Top-K Retrieval

**Problem**: Fixed `RAG_TOP_K=5` truncated results even for "show all" queries.

**Solution**: Dynamic top_k based on query type:

```python
# config.py
RAG_TOP_K = 10        # Default increased from 5
RAG_TOP_K_LIST = 20   # For "list all", "show all" queries

# qa_chain.py
def _get_dynamic_top_k(query: str) -> int:
    if _is_list_query(query):
        return RAG_TOP_K_LIST  # 20 for list queries
    return RAG_TOP_K  # 10 for normal queries
```

### Query Type Detection

**New Helper Functions**:

```python
# Existence queries (yes/no)
_EXISTENCE_PATTERNS = [
    r"^do we have", r"^is there", r"^are there",
    r"^does .* exist", r"^has .* been", r"^have we"
]

def _is_existence_query(query: str) -> bool:
    """Detect yes/no existence questions."""
    q_lower = query.lower().strip()
    return any(re.search(p, q_lower) for p in _EXISTENCE_PATTERNS)

# List queries (need more results)
_LIST_KEYWORDS = ["all", "list", "show all", "every", "find all"]

def _is_list_query(query: str) -> bool:
    """Detect 'list all' type queries."""
    return any(kw in query.lower() for kw in _LIST_KEYWORDS)
```

### Empty Result Handling

**Critical Fix**: For existence queries with no results, return definitive "No":

```python
if is_existence and not sources and strategy != "sql":
    search_term = _extract_search_term(query)
    answer_text = f"No, there are no invoices matching '{search_term}' in the system."
    return {
        "answer": answer_text,
        "definitive_no": True,  # Flag for UI
        ...
    }
```

### Entity Tracking in Memory

**Problem**: Follow-up questions failed because system didn't track context.

**Solution**: Enhanced ConversationMemory with entity tracking:

```python
class ConversationMemory:
    def __init__(self, max_turns: int = 5):
        self.turns: List[Dict[str, Any]] = []
        self.entities: Dict[str, Any] = {}  # Track invoice_number, vendor_name
    
    def add_turn(self, question: str, answer: str, entities: Dict = None):
        self.turns.append({
            "question": question,
            "answer": answer,
            "entities": entities or {}
        })
        if entities:
            self.entities.update(entities)  # Persist across turns
```

### Invoice Number Normalization

**Problem**: "GST001" didn't match "GST-001" in BM25 search.

**Solution**: Normalize invoice numbers during search:

```python
def _normalize_invoice_number(text: str) -> str:
    """GST-001, GST/001, GST 001 → GST001"""
    return re.sub(r'[-/\s]', '', text.upper())

def search(self, query: str, top_k: int = 5) -> list[dict]:
    # Search with both original and normalized queries
    scores = self.bm25.get_scores(_tokenise(query))
    norm_scores = self.bm25.get_scores(_tokenise(_normalize_invoice_number(query)))
    scores = [max(s1, s2) for s1, s2 in zip(scores, norm_scores)]
```

### Production Test Cases

**New test categories added** (10 cases):

| Category | Example Question | Expected Behavior |
|----------|-----------------|-------------------|
| `existence_negative` | "Do we have invoices from XYZ Corp?" | Answer "No, not found" |
| `existence_positive` | "Do we have invoices from NIREL?" | Answer "Yes" + details |
| `count_zero` | "How many invoices from Fake Inc?" | Answer "0" or "None" |
| `list_all` | "Show all vendors" | Use TOP_K=20, show count |
| `comparison` | "Which vendor has most invoices?" | SQL aggregation |
| `action_oriented` | "Show failed validations" | Business-actionable |

### Response Metadata

**Enhanced return structure**:

```python
return {
    "answer": answer_text,
    "strategy": strategy,
    "sources": sources,
    "is_existence_query": True,     # Query type flag
    "definitive_no": True,          # Confident negative answer
    "total_results": 35,            # Total matches found
    "truncated": True,              # Results were limited
    "showing": 10,                  # Number shown
}
```

### Configuration Reference

**Updated defaults** in `core/config.py`:

| Setting | Old Value | New Value | Purpose |
|---------|-----------|-----------|---------|
| `RAG_TOP_K` | 5 | 10 | Default retrieval limit |
| `RAG_TOP_K_LIST` | N/A | 20 | For "list all" queries |

---

### Unit Testing

- **pytest Framework**: Test discovery and execution
- **Fixtures**: Reusable test data
- **Mocking**: Isolate dependencies
- **Coverage**: Code coverage measurement

**Example Unit Test**:
```python
import pytest
from core.validator import validate_gstin

def test_valid_gstin():
    assert validate_gstin("27AAPFU0939F1ZV") == True

def test_invalid_gstin_length():
    assert validate_gstin("27AAPFU0939F") == False

def test_invalid_gstin_format():
    assert validate_gstin("XX123456789012X") == False
```

---

## Summary: Critical Skills for RAG Development

### Must-Have Skills (Priority 1)

1. **Python Programming**: Advanced proficiency with async, type hints, OOP
2. **Vector Embeddings**: Sentence-Transformers, semantic similarity
3. **ChromaDB**: Vector database operations, indexing, querying
4. **BM25 Search**: Keyword-based retrieval, tokenization
5. **LLM Integration**: Ollama API, prompt engineering, JSON parsing
6. **Query Routing**: Intent detection, strategy selection
7. **FastAPI**: Async endpoints, file uploads, CORS
8. **SQLAlchemy**: ORM, query building, relationships
9. **Pydantic**: Data validation, schema definition

### Important Skills (Priority 2)

10. **OCR Systems**: PaddleOCR, Tesseract, image preprocessing
11. **PDF Processing**: pdfplumber, PyMuPDF, table extraction
12. **Conversation Memory**: Turn-based context management
13. **Hybrid Ranking**: Reciprocal Rank Fusion
14. **Re-ranking**: Cross-encoder models, relevance scoring
15. **Streamlit**: UI components, session state, caching
16. **Data Serialization**: JSON, Excel export
17. **Logging**: Python logging module, handlers
18. **Evaluation**: Hit@K, MRR, F1 score

### Nice-to-Have Skills (Priority 3)

19. **Docker**: Containerization, docker-compose
20. **Git**: Branching, pull requests, merge strategies
21. **OpenCV**: Advanced image processing
22. **Pandas**: Data analysis, aggregation
23. **Plotly**: Data visualization, interactive charts
24. **Invoice Domain**: GST knowledge, accounting concepts
25. **Testing**: pytest, mocking, regression testing

---

## Recommended Learning Path

### Phase 1: Foundations (Weeks 1-2)
- Python async programming
- Pydantic data validation
- SQLAlchemy ORM basics
- Vector embeddings concepts

### Phase 2: RAG Core (Weeks 3-4)
- ChromaDB operations
- BM25 keyword search
- Sentence-Transformers
- Query routing logic

### Phase 3: LLM Integration (Weeks 5-6)
- Ollama API usage
- Prompt engineering
- JSON parsing strategies
- Hallucination mitigation

### Phase 4: Web Development (Weeks 7-8)
- FastAPI endpoints
- Streamlit UI components
- File upload handling
- API testing

### Phase 5: Document Processing (Weeks 9-10)
- OCR engines (PaddleOCR, Tesseract)
- PDF text extraction
- Table detection
- Image preprocessing

### Phase 6: Advanced RAG (Weeks 11-12)
- Hybrid retrieval strategies
- Re-ranking algorithms
- Conversation memory
- Query expansion (HyDE)

### Phase 7: Evaluation & Optimization (Weeks 13-14)
- Evaluation metrics
- Ground truth creation
- Regression testing
- Performance tuning

---

## Resources

### Official Documentation
- **FastAPI**: https://fastapi.tiangolo.com/
- **Streamlit**: https://docs.streamlit.io/
- **ChromaDB**: https://docs.trychroma.com/
- **Sentence-Transformers**: https://www.sbert.net/
- **SQLAlchemy**: https://docs.sqlalchemy.org/
- **Pydantic**: https://docs.pydantic.dev/

### Tutorials & Courses
- LangChain RAG Tutorial: https://python.langchain.com/docs/use_cases/question_answering/
- Sentence-Transformers Course: https://huggingface.co/course/chapter5/
- FastAPI Full Course: https://testdriven.io/courses/tdd-fastapi/

### Research Papers
- "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (Lewis et al., 2020)
- "Dense Passage Retrieval for Open-Domain Question Answering" (Karpukhin et al., 2020)
- "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT" (Khattab & Zaharia, 2020)

### Community
- ChromaDB Discord: https://discord.gg/MMeYNTmh3x
- LangChain Community: https://github.com/langchain-ai/langchain
- Hugging Face Forums: https://discuss.huggingface.co/

---

## 14. Anti-Hallucination Framework

### Architecture Overview

Five layers prevent confabulation from qwen2.5:3b, the QA LLM:

| Layer | Mechanism | Location |
|-------|-----------|----------|
| 1 | Prompt grounding — every claim must be verbatim from context | `qa_chain.py:_SYSTEM_PROMPT` |
| 2 | Entity cross-validation — post-answer entity verification | `rag/hallucination_guard.py` |
| 3 | Confidence scoring — numeric confidence 0.0–1.0 per answer | `qa_chain.py:answer()` |
| 4 | Factual override — deterministic fallback on false negatives | `qa_chain.py:_build_factual_answer_from_sources()` |
| 5 | Monitoring — JSONL event log + daily summary endpoint | `rag/hallucination_monitor.py` |

### Key Classes and Functions

**rag/hallucination_guard.py**
- `HallucinationGuard.validate_answer(answer, context, sources) -> dict`
  - Returns: `verified`, `hallucination_score`, `unverified_claims`, `confidence`
- `HallucinationGuard.check_false_negative(answer, sources) -> bool`

**rag/qa_chain.py additions**
- `_build_factual_answer_from_sources(results: List[dict]) -> str`
  - Deterministic answer builder from metadata — no LLM call, always factually correct.
- `calculate_confidence(strategy, results, hallucination_score) -> float`

**rag/hallucination_monitor.py**
- `log_answer_event(query, result_dict) -> None`
- `daily_summary() -> dict`

### Return Dict Contract for qa_chain.answer()

All callers must handle these fields (new in April 2026):

```python
{
    "answer": str,
    "strategy": str,
    "sources": List[str],
    "confidence": float,            # 0.0–1.0
    "hallucination_score": float,   # 0.0 = fully grounded
    "answer_overridden": bool,      # True if factual fallback was used
    "override_reason": str | None,  # Why override fired
    "is_existence_query": bool,
    "total_results": int,
}
```

### Anti-Hallucination Rules for All Engineers

1. `LLM_TEMPERATURE` MUST remain `0` for all QA calls — never increase.
2. Never remove the `CRITICAL RULE` block from `_SYSTEM_PROMPT`.
3. Never use HyDE for SQL-routed queries (SQL is already deterministic).
4. Context format MUST use `=== INVOICE RECORD N ===` delimiters.
5. Strategy lock MUST be applied whenever BM25/vector sources are present.
6. `_build_factual_answer_from_sources()` must never call the LLM.

---

## 15. Production Readiness & Bug Fix Registry

### P0 Bugs Fixed (April 2026)

| Bug | Description | Fix Location |
|-----|-------------|--------------|
| #1 | vendor.address extraction added | `_clean_extracted_fields()`, regex fallback |
| #2 | bill_to.address backfill for null LLM returns | `_clean_extracted_fields()` |
| #3 | ship_to.address extraction implemented | `_clean_extracted_fields()` |
| #4 | Prompt changed: positive dual instruction for address fields | `EXTRACTION_PROMPT` |
| #5 | BM25 indexes city/state; city-boost in search() | `bm25_retriever.py` |
| #6 | DB ingest count validation; vendor_name UPPER() normalised | `run_db_ingest.py`, `db.py` |
| #7 | Router receives memory_entities; follow-up detection added | `router.py`, `qa_chain.py` |
| #8 | HallucinationGuard validates every LLM answer | `hallucination_guard.py` |
| #24 | Strategy lock prevents LLM ignoring BM25/vector context | `qa_chain.py` |
| #25 | Ingest count validation; --force re-ingest flag | `run_db_ingest.py` |
| #26 | 30s timeout guard on all retrieval; follow-up uses memory_only | `qa_chain.py` |
| #27 | Vector strategy subject to strategy lock; factual fallback | `qa_chain.py` |
| #28 | Garbage invoice_number validation in extractor and db.py | `llm_extractor.py`, `db.py` |

### Production Readiness Checklist

- [x] All P0 bugs fixed and unit tests passing
- [ ] `hallucination_log.jsonl` rotating daily
- [ ] Confidence badge visible in Streamlit UI (green/yellow/red)
- [ ] Rate limiting active on `/ask` endpoint (10 req/min/IP)
- [ ] Session persistence using SQLite `rag_sessions` table
- [ ] Audit log table populated on every invoice insert
- [ ] Date normalisation migration run on existing data
- [ ] Vendor name `UPPER()` normalisation applied to existing rows
- [ ] BM25 index rebuilt after all fixes
- [ ] ChromaDB collection recreated with HNSW tuning
- [ ] p95 query latency < 5s verified under 100 concurrent test queries
- [ ] 83-case test suite (73 existing + 10 new regression) at 95%+ pass rate

### Non-Negotiable Production Parameters

```python
LLM_TEMPERATURE          = 0      # Never increase for QA calls
RETRIEVAL_TIMEOUT_SEC    = 30     # Hard ceiling on all retrieval
OLLAMA_CALL_TIMEOUT_SEC  = 60     # Hard ceiling on LLM generation
MAX_INVOICE_CHARS        = 30000  # Multi-page extraction limit
BM25_EXACT_MATCH_SCORE   = 999    # For GSTIN/invoice number direct hits
RATE_LIMIT_PER_MIN       = 10     # Per IP on /ask endpoint
RAG_TOP_K                = 10     # Default retrieval limit
RAG_TOP_K_LIST           = 20     # For "list all" / "show all" queries
```

---

**Document Version**: 1.1  
**Contributors**: AI-Assisted Documentation System  
**Last Review Date**: April 2026
