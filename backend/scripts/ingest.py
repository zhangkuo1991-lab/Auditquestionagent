"""
Offline Ingestion Script
------------------------
Run this once to process the AICPA AU-C Standards PDF and build the BM25 index.
The index is saved to backend/data/ and automatically loaded by the FastAPI server.

Usage:
    cd audit-app/backend
    python scripts/ingest.py                         # uses default PDF in data/standards/
    python scripts/ingest.py --pdf path/to/file.pdf  # custom PDF path

The script takes a few minutes for the full 2000+ page document.
Progress is printed to the console.
"""

import sys
import os
import argparse
from pathlib import Path
from glob import glob

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.retriever import retriever


def find_default_pdf() -> str | None:
    standards_dir = Path(__file__).parent.parent / "data" / "standards"
    pdfs = list(standards_dir.glob("*.pdf"))
    if pdfs:
        # Prefer files with 'au-c' in the name
        for p in pdfs:
            if "au-c" in p.name.lower() or "aicpa" in p.name.lower():
                return str(p)
        return str(pdfs[0])
    return None


def main():
    parser = argparse.ArgumentParser(description="Ingest AICPA AU-C Standards PDF into BM25 index")
    parser.add_argument("--pdf", type=str, default=None, help="Path to PDF file")
    args = parser.parse_args()

    pdf_path = args.pdf or find_default_pdf()

    if not pdf_path:
        print("❌ No PDF found. Place a PDF in backend/data/standards/ or use --pdf <path>")
        sys.exit(1)

    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    print(f"📄 Ingesting: {pdf_path}")
    print("⏳ This may take 2–5 minutes for a large PDF...\n")

    try:
        status = retriever.ingest(pdf_path, source_name=os.path.basename(pdf_path))
        print(f"\n✅ Ingestion complete!")
        print(f"   Chunks indexed : {status['chunk_count']:,}")
        print(f"   Source         : {status['source']}")
        print(f"   Index saved to : backend/data/bm25_index.json")
        print(f"\n🚀 Start the server and the RAG index will load automatically.")
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
