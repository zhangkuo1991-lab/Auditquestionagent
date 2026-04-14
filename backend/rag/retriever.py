"""
Retriever
---------
High-level interface for the RAG pipeline.

Manages:
  - Loading / saving the BM25 index and chunk store
  - The ingest() pipeline (PDF → chunks → index)
  - retrieve() for query-time context injection
  - format_context() to build the prompt block sent to the audit agent
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional

from .pdf_processor import process_pdf
from .bm25_index import BM25Index

# ── Default paths ─────────────────────────────────────────────────────────────
_HERE       = Path(__file__).parent.parent   # backend/
DATA_DIR    = _HERE / "data"
INDEX_PATH  = DATA_DIR / "bm25_index.json"
CHUNKS_PATH = DATA_DIR / "chunks.json"
STATUS_PATH = DATA_DIR / "ingest_status.json"


class Retriever:
    """
    Singleton-friendly retriever. Create one instance and reuse it across requests.
    """

    def __init__(self):
        self._index:  BM25Index = BM25Index()
        self._chunks: List[Dict] = []
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── Status ────────────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return not self._index.is_empty

    def get_status(self) -> Dict:
        if STATUS_PATH.exists():
            with open(STATUS_PATH) as f:
                return json.load(f)
        return {"indexed": False, "chunk_count": 0, "source": None}

    # ── Load (called on server startup) ───────────────────────────────────────

    def try_load(self) -> bool:
        """Load existing index from disk if available. Returns True if loaded."""
        if INDEX_PATH.exists() and CHUNKS_PATH.exists():
            try:
                self._index.load(str(INDEX_PATH))
                with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
                    self._chunks = json.load(f)
                print(f"[Retriever] Loaded {len(self._chunks)} chunks from disk.")
                return True
            except Exception as e:
                print(f"[Retriever] Failed to load index: {e}")
        return False

    # ── Ingest ────────────────────────────────────────────────────────────────

    def ingest(self, pdf_path: str, source_name: Optional[str] = None) -> Dict:
        """
        Full ingestion pipeline:
          1. Extract + chunk the PDF
          2. Build BM25 index
          3. Persist index and chunks to disk
        """
        print(f"[Retriever] Starting ingestion of: {pdf_path}")

        # Step 1: Process PDF into chunks
        chunks = process_pdf(pdf_path, chunk_size=600, overlap=100)
        if not chunks:
            raise ValueError("PDF processing returned no chunks.")

        # Step 2: Build BM25 index
        texts    = [c["text"] for c in chunks]
        metadata = [{k: v for k, v in c.items() if k != "text"} for c in chunks]
        # Keep text in metadata too so we can return it at query time
        for i, chunk in enumerate(chunks):
            metadata[i]["text"] = chunk["text"]

        self._index.build(texts, metadata)
        self._chunks = chunks

        # Step 3: Persist
        self._index.save(str(INDEX_PATH))
        with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)

        status = {
            "indexed":     True,
            "chunk_count": len(chunks),
            "source":      source_name or os.path.basename(pdf_path),
        }
        with open(STATUS_PATH, "w") as f:
            json.dump(status, f)

        print(f"[Retriever] Ingestion complete. {len(chunks)} chunks indexed.")
        return status

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Return top_k most relevant chunks for the query.
        Returns [] if no index is loaded.
        """
        if not self.is_ready:
            return []
        return self._index.retrieve(query, top_k=top_k)

    # ── Format for prompt injection ───────────────────────────────────────────

    def format_context(self, results: List[Dict]) -> str:
        """
        Format retrieved chunks into a prompt block for the audit agent.
        Includes section reference and page numbers for citation.
        """
        if not results:
            return ""

        lines = [
            "=== RETRIEVED CONTEXT FROM OFFICIAL AICPA AU-C STANDARDS (2025) ===",
            "Use this content to answer the question. Cite section numbers and paragraphs.\n",
        ]

        for i, r in enumerate(results, 1):
            section    = r.get("section", "")
            title      = r.get("title", "")
            subsection = r.get("subsection", "")
            pages      = r.get("pages", [])
            text       = r.get("text", "")

            page_ref = f"p. {pages[0]}" if len(pages) == 1 else f"pp. {pages[0]}–{pages[-1]}" if pages else ""
            sub_ref  = f" › {subsection}" if subsection else ""

            lines.append(
                f"[{i}] {section} — {title}{sub_ref} ({page_ref})\n"
                f"{text}\n"
            )

        lines.append("=== END OF RETRIEVED CONTEXT ===")
        return "\n".join(lines)

    def sources_for_response(self, results: List[Dict]) -> List[Dict]:
        """Return lightweight source objects for the API response (no full text)."""
        return [
            {
                "section":  r.get("section", ""),
                "title":    r.get("title", ""),
                "pages":    r.get("pages", []),
                "score":    r.get("score", 0),
            }
            for r in results
        ]


# ── Module-level singleton ────────────────────────────────────────────────────
retriever = Retriever()
