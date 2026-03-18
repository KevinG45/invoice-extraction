"""
Run the Invoice RAG Agent.

Examples:
  python run_rag_agent.py --index-dir outputs/extractions --ask "What is the total amount of invoice GST-001?"
  python run_rag_agent.py --index-dir outputs/extractions --interactive
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rag.agent import InvoiceRAGAgent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Invoice RAG Agent runner")
    parser.add_argument(
        "--index-dir",
        default="outputs/extractions",
        help="Directory containing extraction JSON files",
    )
    parser.add_argument(
        "--ask",
        default=None,
        help="Single question to ask after indexing",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start an interactive Q&A chat loop",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = InvoiceRAGAgent()

    index_dir = Path(args.index_dir)
    if index_dir.exists():
        files, chunks, errors = agent.bulk_index_directory(index_dir)
        print(f"Indexed files: {files}, chunks: {chunks}")
        if errors:
            print("Indexing errors:")
            for err in errors:
                print(f"- {err}")
    else:
        print(f"Index directory not found: {index_dir}")

    if args.ask:
        result = agent.ask(args.ask)
        print("\nAnswer:")
        print(result.get("answer", ""))
        sources = result.get("sources", [])
        if sources:
            print("Sources:", ", ".join(sources))

    if args.interactive:
        agent.interactive_chat()


if __name__ == "__main__":
    main()
