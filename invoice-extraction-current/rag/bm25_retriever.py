"""
BM25 keyword search retriever for invoice extractions.

Builds a BM25Okapi index over extracted invoice JSON files,
enabling fast keyword-based search as a complement to the
ChromaDB vector search layer.

Enhanced with:
- Stopword removal (English)
- Porter stemming for better recall
- Richer document text (includes all chunk types)
- City/location extraction for geo queries (Bug #5)
- GSTIN exact-match boosting (Bug #12)
- Invoice number exact-match boosting (Bug #30)
- Thread-safe index access (Bug P0-8)
"""

import json
import pickle
import re
import threading
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

# FIXED: Bug P0-8 — Thread-safe index access
_index_lock = threading.RLock()

# ── Lightweight NLP helpers (no NLTK dependency) ──────────────────────────

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "was", "are", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "can", "could",
    "not", "no", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "its", "our", "their", "what", "which", "who", "whom", "how",
    "when", "where", "why", "if", "then", "so", "than", "too", "very",
    "just", "about", "above", "after", "before", "below", "between",
    "into", "through", "during", "each", "few", "more", "most", "other",
    "some", "such", "only", "own", "same", "also", "any", "both",
})

# Simple Porter-style suffix stripping (covers 80% of cases without NLTK)
_SUFFIX_RULES = [
    (r"ies$", "y"),       # companies -> company
    (r"ves$", "f"),       # invoices -> invoicf (close enough for matching)
    (r"ses$", "s"),       # addresses -> address
    (r"ing$", ""),        # shipping -> shipp
    (r"tion$", "t"),      # validation -> validat
    (r"ment$", ""),       # payment -> pay
    (r"ness$", ""),       # business -> busi
    (r"able$", ""),       # payable -> pay
    (r"ful$", ""),        # successful -> success
    (r"ed$", ""),         # validated -> validat
    (r"ly$", ""),         # currently -> current
    (r"er$", ""),         # vendor -> vend (but still matches)
    (r"s$", ""),          # invoices -> invoice
]

_SUFFIX_PATTERNS = [(re.compile(p), r) for p, r in _SUFFIX_RULES]


# FIXED: Bug #5 - City names for location-based queries
_CITY_NAMES = frozenset({
    # Major Indian cities
    "bangalore", "bengaluru", "hyderabad", "chennai", "mumbai", "delhi",
    "pune", "kolkata", "ahmedabad", "jaipur", "lucknow", "kanpur",
    "nagpur", "indore", "thane", "bhopal", "visakhapatnam", "vadodara",
    "ghaziabad", "ludhiana", "agra", "nashik", "faridabad", "meerut",
    "rajkot", "varanasi", "srinagar", "aurangabad", "dhanbad", "amritsar",
    "allahabad", "ranchi", "howrah", "coimbatore", "jabalpur", "gwalior",
    "vijayawada", "jodhpur", "madurai", "raipur", "kota", "chandigarh",
    "guwahati", "solapur", "hubli", "mysore", "tiruchirappalli", "bareilly",
    "aligarh", "tiruppur", "moradabad", "jalandhar", "bhubaneswar", "salem",
    "warangal", "guntur", "bhiwandi", "saharanpur", "gorakhpur", "bikaner",
    "amravati", "noida", "jamshedpur", "bhilai", "cuttack", "firozabad",
    "kochi", "bhavnagar", "dehradun", "durgapur", "asansol", "nanded",
    "kolhapur", "ajmer", "akola", "gulbarga", "jamnagar", "ujjain",
    "loni", "siliguri", "jhansi", "ulhasnagar", "nellore", "jammu",
    "sangli", "belgaum", "mangalore", "erode", "tirunelveli", "malegaon",
    "gaya", "udaipur", "maheshtala", "davanagere", "kozhikode", "kurnool",
    "secunderabad", "quthbullapur", "quthubullapur",  # Both spellings
    # Also include some common state names
    "karnataka", "telangana", "andhra", "maharashtra", "tamil", "kerala",
    "gujarat", "rajasthan", "uttar", "madhya", "west", "bihar", "odisha",
    "punjab", "haryana", "uttarakhand", "jharkhand", "chhattisgarh", "assam",
})

# PIN code pattern (6-digit Indian postal codes)
_PIN_RE = re.compile(r"\b(\d{6})\b")

# State patterns
_STATE_RE = re.compile(r"(?:state[:\s]+|,\s*)([A-Za-z\s]+?)(?:,|\s*-?\s*\d{6}|\s*$)", re.IGNORECASE)


def _extract_city_from_address(address: Optional[str]) -> Optional[str]:
    """
    Extract city name from an address string.
    # FIXED: Bug #5 - City extraction for location queries
    
    Returns the first recognized city name found, or None.
    """
    if not address:
        return None
    
    addr_lower = address.lower()
    
    # Check for known city names
    for city in _CITY_NAMES:
        if city in addr_lower:
            # Return the properly capitalized version
            return city.title()
    
    return None


def _extract_pin_from_address(address: Optional[str]) -> Optional[str]:
    """Extract 6-digit PIN code from address."""
    if not address:
        return None
    match = _PIN_RE.search(address)
    return match.group(1) if match else None


def _extract_state_from_address(address: Optional[str]) -> Optional[str]:
    """Extract state name from address."""
    if not address:
        return None
    match = _STATE_RE.search(address)
    if match:
        state = match.group(1).strip()
        # Clean up common prefixes
        state = re.sub(r"^(state\s*(name|code)?\s*:?\s*)", "", state, flags=re.IGNORECASE)
        return state.title() if state else None
    return None


def _normalize_invoice_number(text: str) -> str:
    """Normalize invoice numbers for fuzzy matching.
    
    FIXED: Bug #9 — Enhanced invoice number normalization
    
    Handles common variations:
    - GST-001, GST/001, GST 001 → GST001
    - INV-2024-001 → INV2024001
    - Leading zeros: GST001 vs GST0001 vs GST1 → all variations indexed
    - Case variations: gst001 vs GST001 → GST001
    - Slash vs dash: GST/001 vs GST-001 → GST001
    """
    # Remove common separators and uppercase
    normalized = re.sub(r'[-/\s]', '', text.upper())
    return normalized


def _generate_invoice_number_variants(inv_num: str) -> list[str]:
    """
    FIXED: Bug #9 — Generate all common variants of an invoice number for fuzzy matching.
    
    Given "GST001", generates: ["GST001", "gst001", "GST-001", "GST/001", "GST1", "GST0001"]
    """
    if not inv_num:
        return []
    
    variants = set()
    
    # Base normalized form (uppercase, no separators)
    normalized = re.sub(r'[-/\s]', '', inv_num.upper())
    variants.add(normalized)
    variants.add(normalized.lower())
    
    # Find prefix and numeric parts
    match = re.match(r'^([A-Za-z]+)[-/\s]*(\d+)$', inv_num)
    if match:
        prefix, num = match.groups()
        prefix_upper = prefix.upper()
        prefix_lower = prefix.lower()
        
        # Different separator variants
        variants.add(f"{prefix_upper}{num}")
        variants.add(f"{prefix_upper}-{num}")
        variants.add(f"{prefix_upper}/{num}")
        variants.add(f"{prefix_lower}{num}")
        
        # Leading zero variants (strip and add)
        num_stripped = num.lstrip('0') or '0'
        if num_stripped != num:
            # Original has leading zeros, add stripped version
            variants.add(f"{prefix_upper}{num_stripped}")
            variants.add(f"{prefix_lower}{num_stripped}")
        
        # Add with 2, 3, 4 digit padding
        for width in [2, 3, 4, 5]:
            padded = num_stripped.zfill(width)
            variants.add(f"{prefix_upper}{padded}")
            variants.add(f"{prefix_lower}{padded}")
    
    return list(variants)


def _stem(word: str) -> str:
    """Apply simple suffix stripping. Good enough for BM25 matching."""
    if len(word) <= 3:
        return word
    for pattern, replacement in _SUFFIX_PATTERNS:
        stemmed = pattern.sub(replacement, word)
        if stemmed != word and len(stemmed) >= 3:
            return stemmed
    return word


def _tokenise(text: str, for_indexing: bool = False) -> list[str]:
    """Tokenise with lowercasing, stopword removal, and stemming.
    
    FIXED: Bug #9 — Enhanced tokenization with invoice number variants.
    
    Keeps alphanumeric sequences together (important for GSTINs, invoice numbers).
    Also creates normalized versions of invoice-like patterns.
    """
    # Safety check for None/empty text
    if not text:
        return []
    
    text_lower = text.lower()
    
    # Split on whitespace and punctuation, keep alphanumeric sequences intact
    # This preserves tokens like "36ARKPC6820F1ZZ" as a single token
    tokens = re.findall(r"[a-zA-Z0-9]+", text_lower)
    
    # If indexing, also add normalized versions of invoice-like patterns
    # FIXED: Bug #9 — Generate all variants for better fuzzy matching
    if for_indexing:
        # Find invoice-like patterns and add all variants
        invoice_patterns = re.findall(r"(?:gst|inv|bill|po|rec|quot|so)[-/\s]?\d+", text_lower, re.IGNORECASE)
        for pattern in invoice_patterns:
            # Add all variants of this invoice number
            variants = _generate_invoice_number_variants(pattern)
            for variant in variants:
                if variant.lower() not in tokens:
                    tokens.append(variant.lower())
    
    # Remove stopwords, then stem
    return [_stem(t) for t in tokens if t not in _STOPWORDS and len(t) >= 2]


class BM25Retriever:

    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.bm25 = None
        self.metadata: list[dict] = []
        self.corpus: list[list[str]] = []
        self.documents: list[str] = []  # Full document text

    # ── Build ─────────────────────────────────────────────────────────────

    def build_index(self, extractions_dir: str) -> int:
        """Read all JSON extractions and build a BM25 index.

        Returns the number of documents indexed.
        """
        extractions_path = Path(extractions_dir)
        json_files = sorted(extractions_path.glob("*.json"))

        corpus: list[list[str]] = []
        metadata: list[dict] = []
        documents: list[str] = []  # Store full document text for retrieval

        for jf in json_files:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)

            doc_text = self._build_document_string(data)
            tokens = _tokenise(doc_text, for_indexing=True)  # Use indexing mode
            if not tokens:
                continue

            corpus.append(tokens)
            documents.append(doc_text)  # Store the full text
            
            # Extract additional fields for richer metadata
            vendor = data.get("vendor") or {}
            bill_to = data.get("bill_to") or {}
            line_items = data.get("line_items") or []
            
            # FIXED: Bug #5 - Extract city/state/pin from addresses
            vendor_address = vendor.get("address")
            bill_to_address = bill_to.get("address")
            vendor_city = _extract_city_from_address(vendor_address)
            vendor_state = _extract_state_from_address(vendor_address)
            vendor_pin = _extract_pin_from_address(vendor_address)
            bill_to_city = _extract_city_from_address(bill_to_address)
            
            metadata.append({
                "source_file": (data.get("metadata") or {}).get("source_file", jf.name),
                "invoice_id": data.get("invoice_number"),
                "vendor_name": vendor.get("name"),
                "vendor_gstin": vendor.get("tax_id"),  # Store vendor GSTIN
                "vendor_address": vendor_address,
                # FIXED: Bug #5 - Add city/state/pin metadata
                "vendor_city": vendor_city,
                "vendor_state": vendor_state,
                "vendor_pin": vendor_pin,
                "bill_to_name": bill_to.get("name"),
                "bill_to_gstin": bill_to.get("tax_id"),  # Store bill_to GSTIN
                "bill_to_address": bill_to_address,
                "bill_to_city": bill_to_city,
                "invoice_date": data.get("invoice_date"),
                "total_amount": data.get("total_amount"),
                "tax_amount": data.get("tax_amount"),
                "subtotal": data.get("subtotal"),
                "currency": data.get("currency"),
                "line_item_count": len(line_items),
                "line_items_summary": "; ".join(
                    str(item.get("description", ""))[:50] for item in line_items[:5]
                ),  # First 5 line item descriptions
            })

        self.corpus = corpus
        self.metadata = metadata
        self.documents = documents  # Store documents
        self.bm25 = BM25Okapi(corpus) if corpus else None

        # Serialise to disk
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump({"corpus": corpus, "metadata": metadata, "documents": documents}, f)

        return len(corpus)

    # ── Load ──────────────────────────────────────────────────────────────

    def load_index(self):
        """
        Load a previously-built index from disk.
        FIXED: Bug P0-8 — Thread-safe index loading.
        """
        with _index_lock:
            if not self.index_path.exists():
                return
            with open(self.index_path, "rb") as f:
                store = pickle.load(f)
            self.corpus = store["corpus"]
            self.metadata = store["metadata"]
            self.documents = store.get("documents", [])  # Handle old indexes without documents
            self.bm25 = BM25Okapi(self.corpus) if self.corpus else None

    # ── Incremental update ─────────────────────────────────────────────────

    def add_document(self, data: dict, source_filename: str) -> None:
        """
        Add a single extraction result to the index without re-reading all files.
        
        FIXED: Bug P1-6 — Incremental update: only rebuild if batch complete or forced.
        """
        doc_text = self._build_document_string(data)
        tokens = _tokenise(doc_text, for_indexing=True)
        if not tokens:
            return

        self.corpus.append(tokens)
        self.documents.append(doc_text)
        
        vendor = data.get("vendor") or {}
        bill_to = data.get("bill_to") or {}
        line_items = data.get("line_items") or []
        
        # FIXED: Bug #5 - Extract city/state/pin from addresses
        vendor_address = vendor.get("address")
        bill_to_address = bill_to.get("address")
        vendor_city = _extract_city_from_address(vendor_address)
        vendor_state = _extract_state_from_address(vendor_address)
        vendor_pin = _extract_pin_from_address(vendor_address)
        bill_to_city = _extract_city_from_address(bill_to_address)
        
        self.metadata.append({
            "source_file": source_filename,
            "invoice_id": data.get("invoice_number"),
            "vendor_name": vendor.get("name"),
            "vendor_gstin": vendor.get("tax_id"),
            "vendor_address": vendor_address,
            # FIXED: Bug #5 - Add city/state/pin metadata
            "vendor_city": vendor_city,
            "vendor_state": vendor_state,
            "vendor_pin": vendor_pin,
            "bill_to_name": bill_to.get("name"),
            "bill_to_gstin": bill_to.get("tax_id"),
            "bill_to_address": bill_to_address,
            "bill_to_city": bill_to_city,
            "invoice_date": data.get("invoice_date"),
            "total_amount": data.get("total_amount"),
            "tax_amount": data.get("tax_amount"),
            "subtotal": data.get("subtotal"),
            "currency": data.get("currency"),
            "line_item_count": len(line_items),
            "line_items_summary": "; ".join(
                str(item.get("description", ""))[:50] for item in line_items[:5]
            ),
        })
        # Mark that index needs rebuild (deferred until save or search)
        self._needs_rebuild = True
    
    def commit(self) -> None:
        """
        Commit pending changes: rebuild BM25 if needed and save to disk.
        
        FIXED: Bug P1-6 — Call this after batch additions for efficiency.
        """
        if getattr(self, '_needs_rebuild', False) and self.corpus:
            with _index_lock:
                self.bm25 = BM25Okapi(self.corpus)
                self.index_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.index_path, "wb") as f:
                    pickle.dump({"corpus": self.corpus, "metadata": self.metadata, "documents": self.documents}, f)
                self._needs_rebuild = False

    # ── Search ────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Return top_k results sorted by BM25 score descending.
        
        Enhanced with:
        - Invoice number normalization and exact matching (Bug #30)
        - GSTIN exact matching (Bug #12)
        - City/location boosting (Bug #5)
        - Thread-safe search (Bug P0-8)
        - Lazy commit for pending changes (Bug P1-6)
        """
        # Safety check for None query
        if not query:
            return []
        
        # FIXED: Bug P1-6 — Commit pending changes before search
        if getattr(self, '_needs_rebuild', False):
            self.commit()
        
        # FIXED: Bug P0-8 — Thread-safe search
        with _index_lock:
            if self.bm25 is None:
                return []

            tokens = _tokenise(query)
            if not tokens:
                return []

            scores = list(self.bm25.get_scores(tokens))  # Make mutable
            
            # Also try normalized invoice number search for better matching
            # E.g., "GST001" should match "GST-001"
            normalized_query = _normalize_invoice_number(query)
            if normalized_query != query.upper():
                norm_tokens = _tokenise(normalized_query)
                if norm_tokens:
                    norm_scores = self.bm25.get_scores(norm_tokens)
                # Take the max of both score sets
                scores = [max(s1, s2) for s1, s2 in zip(scores, norm_scores)]

        # FIXED: Bug #12 - GSTIN exact match (bypass BM25, force score=999)
        gstin_match = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b", query.upper())
        if gstin_match:
            gstin = gstin_match.group(0)
            for i, m in enumerate(self.metadata):
                vendor_gstin = (m.get("vendor_gstin") or "").upper()
                bill_to_gstin = (m.get("bill_to_gstin") or "").upper()
                if vendor_gstin == gstin or bill_to_gstin == gstin:
                    scores[i] = 999  # Guaranteed top result

        # FIXED: Bug #30 - Invoice number exact match (force score=999)
        inv_match = re.search(r"\b(GST|INV|BILL|PO|REC|QUOT|SO)[-/]?\d+\b", query, re.IGNORECASE)
        if inv_match:
            inv_num = inv_match.group(0)
            inv_norm = _normalize_invoice_number(inv_num)
            for i, m in enumerate(self.metadata):
                meta_inv = m.get("invoice_id") or ""
                meta_inv_norm = _normalize_invoice_number(meta_inv)
                source_file = m.get("source_file") or ""
                source_norm = _normalize_invoice_number(source_file.split(".")[0])
                if meta_inv_norm == inv_norm or source_norm == inv_norm:
                    scores[i] = 999  # Guaranteed top result
        
        # Also check for file pattern (e.g., "GST001.pdf")
        file_match = re.search(r"\b([\w-]+)\.(pdf|json)\b", query, re.IGNORECASE)
        if file_match:
            file_base = file_match.group(1).upper()
            for i, m in enumerate(self.metadata):
                source_file = (m.get("source_file") or "").upper()
                if file_base in source_file:
                    scores[i] = 999

        # FIXED: Bug #5 - City boosting (2x multiplier for city matches)
        query_lower = query.lower()
        query_cities = [city for city in _CITY_NAMES if city in query_lower]
        if query_cities:
            for i, m in enumerate(self.metadata):
                vendor_city = (m.get("vendor_city") or "").lower()
                bill_to_city = (m.get("bill_to_city") or "").lower()
                for city in query_cities:
                    if city == vendor_city or city == bill_to_city:
                        scores[i] *= 2.0  # Boost city matches

        # Rank and return results
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for idx, score in ranked:
            if score <= 0:
                continue
            entry = {"score": round(float(score), 4), **self.metadata[idx]}
            # Include full document text if available
            if self.documents and idx < len(self.documents):
                entry["text"] = self.documents[idx]
            results.append(entry)
        return results

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _build_document_string(data: dict) -> str:
        """Concatenate all searchable invoice fields into a single string."""
        parts: list[str] = []

        # Include source file name for file-based queries
        metadata = data.get("metadata") or {}
        source_file = metadata.get("source_file")
        if source_file:
            parts.append(str(source_file))

        # Core fields
        for field in ("invoice_number", "invoice_date", "due_date",
                      "total_amount", "subtotal", "tax_amount",
                      "currency", "purchase_order_number", "notes",
                      "payment_terms", "payment_method"):
            val = data.get(field)
            if val is not None:
                parts.append(str(val))

        # Vendor
        vendor = data.get("vendor") or {}
        for vf in ("name", "tax_id", "address", "email", "phone"):
            val = vendor.get(vf)
            if val is not None:
                parts.append(str(val))

        # FIXED: Bug #5 - Add city tokens TWICE for BM25 weight boost
        vendor_address = vendor.get("address")
        vendor_city = _extract_city_from_address(vendor_address)
        if vendor_city:
            parts.append(vendor_city)
            parts.append(vendor_city)  # Duplicate for boost

        # Bill-to
        bill_to = data.get("bill_to") or {}
        for bf in ("name", "tax_id", "address"):
            val = bill_to.get(bf)
            if val is not None:
                parts.append(str(val))
        
        # FIXED: Bug #5 - Add bill_to city tokens TWICE
        bill_to_address = bill_to.get("address")
        bill_to_city = _extract_city_from_address(bill_to_address)
        if bill_to_city:
            parts.append(bill_to_city)
            parts.append(bill_to_city)  # Duplicate for boost

        # FIXED: Bug #31 - Include ALL line item descriptions (not just first 5)
        for item in data.get("line_items") or []:
            desc = item.get("description")
            if desc is not None:
                if isinstance(desc, list):
                    parts.extend(str(d) for d in desc)
                else:
                    parts.append(str(desc))
            hsn = item.get("hsn_sac")
            if hsn is not None:
                parts.append(str(hsn))

        return " ".join(parts)
