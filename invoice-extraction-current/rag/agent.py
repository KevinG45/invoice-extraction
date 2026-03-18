"""
RAG Agent orchestration for invoice Q&A.

This module wraps the lower-level QA chain and adds practical workflows:
- Bulk indexing from exported JSON files
- Single-question answering with source attribution
- Interactive chat mode
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rag.qa_chain import InvoiceQAChain


class InvoiceRAGAgent:
    """High-level orchestrator for invoice RAG operations."""

    def __init__(self) -> None:
        self.qa_chain = InvoiceQAChain()

    def index_extraction_payload(self, payload: Dict, source_name: str) -> int:
        """
        Index a payload in one of the known extraction formats.

        Supported payload shapes:
        1) {"status": "success", "data": {...invoice...}}
        2) {"invoices": [{...}, ...]} (batch export)
        3) {...invoice...} (direct invoice dict)
        """
        indexed = 0

        # API single result format
        if isinstance(payload, dict) and payload.get("status") == "success" and isinstance(payload.get("data"), dict):
            indexed += self.qa_chain.index_invoice(payload["data"], filename=source_name)
            return indexed

        # Batch export format
        if isinstance(payload, dict) and isinstance(payload.get("invoices"), list):
            for i, inv in enumerate(payload["invoices"], start=1):
                inv_name = inv.get("source_file") or f"{source_name}#invoice_{i}"
                indexed += self.qa_chain.index_invoice(inv, filename=str(inv_name))
            return indexed

        # Direct invoice dict fallback
        if isinstance(payload, dict):
            indexed += self.qa_chain.index_invoice(payload, filename=source_name)

        return indexed

    def index_json_file(self, json_path: Path) -> int:
        """Load and index one JSON extraction file."""
        with json_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return self.index_extraction_payload(payload, source_name=json_path.name)

    def bulk_index_directory(self, directory: Path) -> Tuple[int, int, List[str]]:
        """
        Index all JSON files under a directory (recursive).

        Returns:
            (indexed_files, indexed_chunks, errors)
        """
        indexed_files = 0
        indexed_chunks = 0
        errors: List[str] = []

        for json_file in sorted(directory.rglob("*.json")):
            try:
                chunks = self.index_json_file(json_file)
                indexed_files += 1
                indexed_chunks += chunks
            except Exception as exc:
                errors.append(f"{json_file}: {exc}")

        return indexed_files, indexed_chunks, errors

    def ask(self, question: str) -> Dict:
        """Ask one question against the indexed invoice corpus."""
        return self.qa_chain.ask(question)

    def interactive_chat(self) -> None:
        """Simple terminal chat loop for invoice RAG."""
        print("Invoice RAG Agent ready. Type 'exit' to quit.")
        while True:
            question = input("\nYou: ").strip()
            if not question:
                continue
            if question.lower() in {"exit", "quit"}:
                print("Bye.")
                break

            result = self.ask(question)
            print("\nAgent:", result.get("answer", ""))
            sources = result.get("sources", [])
            if sources:
                print("Sources:", ", ".join(sources))
