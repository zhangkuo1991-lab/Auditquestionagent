"""
PDF Processor
-------------
Extracts and chunks the AICPA AU-C Standards PDF into structured segments
for use in the BM25 retrieval index.

Uses pypdf (pure-Python, no system libraries needed).
Install: pip install pypdf

Strategy:
  - Extract text page-by-page
  - Track AU-C section boundaries as we scroll through pages
  - Sliding-window chunk within each section (600 words, 100 overlap)
  - Attach metadata: section number, title, subsection, page numbers
"""

import re
from typing import List, Dict, Optional, Tuple

# ── Regex patterns ────────────────────────────────────────────────────────────

# Matches: "AU-C Sec. 315 — Understanding the Entity..."
_SECTION_RE = re.compile(
    r'AU-C\s+Sec(?:tion|\.?)?\s*(\d+[A-Z]?)\s*[—\-–]+\s*(.+?)(?:\n|$)',
    re.IGNORECASE
)

# Subsection headings
_SUBSECTION_RE = re.compile(
    r'^(Introduction|Objectives?|Definitions?|Requirements?'
    r'|Application and Other Explanatory Material'
    r'|Appendix\s*[A-Z]?|Exhibit)\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Noise to strip (footers, standalone page numbers)
_FOOTER_RE = re.compile(
    r'©\s*\d{4}\s*AICPA[^.\n]*\.?',
    re.IGNORECASE
)


# ── Public API ────────────────────────────────────────────────────────────────

def process_pdf(pdf_path: str, chunk_size: int = 600, overlap: int = 100) -> List[Dict]:
    """
    Full pipeline: PDF → cleaned pages → section-aware chunks.

    Returns a list of chunk dicts:
      {
        "chunk_id":   int,
        "section":    "AU-C 315",
        "title":      "Understanding the Entity and Its Environment...",
        "subsection": "Requirements",
        "text":       "...",
        "pages":      [345, 346],
        "word_count": 598
      }
    """
    print(f"[PDF] Opening {pdf_path}...")
    pages = _extract_pages(pdf_path)
    print(f"[PDF] Extracted {len(pages)} pages.")

    chunks = _chunk_pages(pages, chunk_size=chunk_size, overlap=overlap)
    print(f"[PDF] Created {len(chunks)} chunks.")
    return chunks


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_pages(pdf_path: str) -> List[Dict]:
    """Return list of {page: int, text: str} using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "pypdf is required. Install it with:\n"
            "  pip install pypdf"
        )

    pages = []
    reader = PdfReader(pdf_path)
    total  = len(reader.pages)

    for i, page in enumerate(reader.pages):
        if i % 100 == 0:
            print(f"[PDF]   reading page {i+1}/{total}...")
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""
        cleaned = _clean_page(raw)
        if cleaned:
            pages.append({"page": i + 1, "text": cleaned})

    return pages


def _clean_page(text: str) -> str:
    """Remove footers, standalone page numbers, and extra blank lines."""
    text = _FOOTER_RE.sub("", text)
    # Remove lines that are only digits (page numbers)
    text = re.sub(r'(?m)^\s*\d{1,4}\s*$', '', text)
    # Collapse excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _detect_section(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (section_number, section_title) if an AU-C header is found."""
    m = _SECTION_RE.search(text)
    if m:
        num   = m.group(1).strip()
        title = re.sub(r'\s*\.\s*$', '', m.group(2).strip())
        return f"AU-C {num}", title
    return None, None


def _detect_subsection(text: str) -> Optional[str]:
    m = _SUBSECTION_RE.search(text)
    return m.group(1).strip() if m else None


def _chunk_pages(
    pages: List[Dict],
    chunk_size: int,
    overlap: int,
) -> List[Dict]:
    """
    Walks all pages, tracking the current AU-C section.
    Emits chunks of ~chunk_size words with overlap between consecutive chunks.
    """
    # Stream all paragraphs with their page numbers
    paragraphs: List[Tuple[str, int]] = []
    for page_data in pages:
        for para in re.split(r'\n{2,}', page_data["text"]):
            para = para.strip()
            if para:
                paragraphs.append((para, page_data["page"]))

    # Sliding-window chunking
    chunks: List[Dict] = []
    current_section    = "AU-C Introduction"
    current_title      = "Principles Underlying an Audit"
    current_subsection: Optional[str] = None
    buffer_words: List[str] = []
    buffer_pages: List[int] = []

    def flush(force: bool = False):
        if len(buffer_words) < 30 and not force:
            return
        if not buffer_words:
            return
        chunks.append({
            "section":    current_section,
            "title":      current_title,
            "subsection": current_subsection,
            "text":       " ".join(buffer_words),
            "pages":      sorted(set(buffer_pages)),
            "word_count": len(buffer_words),
        })

    for para, page_num in paragraphs:
        # New AU-C section → flush and reset
        sec, title = _detect_section(para)
        if sec:
            flush(force=True)
            buffer_words       = []
            buffer_pages       = []
            current_section    = sec
            current_title      = title
            current_subsection = None

        sub = _detect_subsection(para)
        if sub:
            current_subsection = sub

        words = para.split()
        buffer_words.extend(words)
        buffer_pages.extend([page_num] * len(words))

        while len(buffer_words) >= chunk_size:
            flush()
            buffer_words = buffer_words[chunk_size - overlap:]
            buffer_pages = buffer_pages[chunk_size - overlap:]

    flush(force=True)

    for i, chunk in enumerate(chunks):
        chunk["chunk_id"] = i

    return chunks
