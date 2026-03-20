"""
BM25 keyword search retriever for invoice extractions.

Builds a BM25Okapi index over extracted invoice JSON files,
enabling fast keyword-based search as a complement to the
ChromaDB vector search layer.
"""

import json
import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi


class BM25Retriever:

    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.bm25 = None
        self.metadata: list[dict] = []
        self.corpus: list[list[str]] = []

    # ── Build ─────────────────────────────────────────────────────────────

    def build_index(self, extractions_dir: str) -> int:
        """Read all JSON extractions and build a BM25 index.

        Returns the number of documents indexed.
        """
        extractions_path = Path(extractions_dir)
        json_files = sorted(extractions_path.glob("*.json"))

        corpus: list[list[str]] = []
        metadata: list[dict] = []

        for jf in json_files:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)

            doc_text = self._build_document_string(data)
            tokens = self._tokenise(doc_text)
            if not tokens:
                continue

            corpus.append(tokens)
            metadata.append({
                "source_file": (data.get("metadata") or {}).get("source_file", jf.name),
                "invoice_id": data.get("invoice_number"),
                "vendor_name": (data.get("vendor") or {}).get("name"),
                "invoice_date": data.get("invoice_date"),
                "total_amount": data.get("total_amount"),
            })

        self.corpus = corpus
        self.metadata = metadata
        self.bm25 = BM25Okapi(corpus)

        # Serialise to disk
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump({"corpus": corpus, "metadata": metadata}, f)

        return len(corpus)

    # ── Load ──────────────────────────────────────────────────────────────

    def load_index(self):
        """Load a previously-built index from disk."""
        with open(self.index_path, "rb") as f:
            store = pickle.load(f)
        self.corpus = store["corpus"]
        self.metadata = store["metadata"]
        self.bm25 = BM25Okapi(self.corpus)

    # ── Incremental update ─────────────────────────────────────────────────

    def add_document(self, data: dict, source_filename: str) -> None:
        """Add a single extraction result to the index without re-reading all files.

        Appends the document to the in-memory corpus, re-instantiates BM25Okapi
        (rank_bm25 has no incremental API), and persists the updated index.

        Args:
            data: The extraction result dict.
            source_filename: Original filename (used in metadata).
        """
        doc_text = self._build_document_string(data)
        tokens = self._tokenise(doc_text)
        if not tokens:
            return

        self.corpus.append(tokens)
        self.metadata.append({
            "source_file": source_filename,
            "invoice_id": data.get("invoice_number"),
            "vendor_name": (data.get("vendor") or {}).get("name"),
            "invoice_date": data.get("invoice_date"),
            "total_amount": data.get("total_amount"),
        })
        self.bm25 = BM25Okapi(self.corpus)

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "wb") as f:
            pickle.dump({"corpus": self.corpus, "metadata": self.metadata}, f)

    # ── Search ────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return top_k results sorted by BM25 score descending."""
        if self.bm25 is None:
            raise RuntimeError("Index not loaded. Call build_index() or load_index() first.")

        tokens = self._tokenise(query)
        scores = self.bm25.get_scores(tokens)

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for idx, score in ranked:
            if score <= 0:
                continue
            entry = {"score": round(float(score), 4), **self.metadata[idx]}
            results.append(entry)
        return results

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _build_document_string(data: dict) -> str:
        """Concatenate searchable invoice fields into a single string."""
        parts: list[str] = []

        for field in ("invoice_number", "invoice_date", "total_amount"):
            val = data.get(field)
            if val is not None:
                parts.append(str(val))

        vendor = data.get("vendor") or {}
        for vf in ("name", "tax_id"):
            val = vendor.get(vf)
            if val is not None:
                parts.append(str(val))

        bill_to = data.get("bill_to") or {}
        if bill_to.get("name"):
            parts.append(str(bill_to["name"]))

        # Line item descriptions
        for item in data.get("line_items") or []:
            desc = item.get("description")
            if desc is None:
                continue
            if isinstance(desc, list):
                parts.extend(str(d) for d in desc)
            else:
                parts.append(str(desc))

        return " ".join(parts)

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        """Whitespace tokenisation with lowercasing."""
        return text.lower().split()
