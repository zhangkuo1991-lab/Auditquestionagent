"""
BM25 Index
----------
Pure-Python implementation of Okapi BM25 — no external dependencies.

BM25 is the industry-standard ranking function used by Elasticsearch,
Lucene, and most production search engines. It performs very well on
structured legal and standards documents.

Formula (per term t, query Q, document D):
  score(D, Q) = Σ IDF(t) × [ f(t,D) × (k1+1) ] / [ f(t,D) + k1×(1-b+b×|D|/avgdl) ]

where:
  f(t, D)  = term frequency of t in D
  |D|      = number of tokens in D
  avgdl    = average document length in the corpus
  k1 = 1.5, b = 0.75 (standard tuning params)
  IDF(t)   = log( (N - n(t) + 0.5) / (n(t) + 0.5) + 1 )
"""

import re
import math
import json
from collections import Counter
from typing import List, Dict, Tuple


# Audit-domain stop words (extend standard English stops with common filler terms)
_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "shall", "should", "may", "might", "must", "can", "could",
    "that", "this", "these", "those", "it", "its", "they", "them", "their",
    "he", "she", "we", "you", "i", "not", "no", "so", "if", "when", "then",
    "such", "any", "all", "each", "other", "also", "which", "who", "what",
    "where", "whether", "there", "than", "into", "about", "up", "out",
    "more", "than", "how", "further", "ref", "par", "see", "paragraph",
})


class BM25Index:
    """
    Stores tokenised documents and their BM25 scores.
    Supports save/load via JSON for persistence between restarts.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b  = b
        # Parallel arrays: index N → corpus[N] (token list) and metadata[N]
        self.corpus:   List[List[str]] = []
        self.metadata: List[Dict]      = []
        self.idf:      Dict[str, float] = {}
        self.avgdl:    float = 1.0

    # ── Build ────────────────────────────────────────────────────────────────

    def build(self, texts: List[str], metadata: List[Dict]) -> None:
        """Tokenise all texts and compute IDF scores."""
        assert len(texts) == len(metadata), "texts and metadata must be same length"

        print(f"[BM25] Tokenising {len(texts)} chunks...")
        self.corpus   = [self.tokenise(t) for t in texts]
        self.metadata = metadata

        total_tokens  = sum(len(d) for d in self.corpus)
        self.avgdl    = total_tokens / len(self.corpus) if self.corpus else 1.0

        # Document frequency per term
        N  = len(self.corpus)
        df = Counter(term for doc in self.corpus for term in set(doc))

        self.idf = {
            term: math.log((N - freq + 0.5) / (freq + 0.5) + 1)
            for term, freq in df.items()
        }
        print(f"[BM25] Index built. Vocabulary size: {len(self.idf):,}")

    # ── Query ────────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> List[Dict]:
        """
        Return up to top_k chunks most relevant to query.

        Each result:
          {
            "score":      float,
            "chunk_id":   int,
            "section":    "AU-C 315",
            "title":      "...",
            "subsection": "Requirements",
            "pages":      [345, 346],
            "snippet":    "first 300 chars of the chunk text..."
          }
        """
        if not self.corpus:
            return []

        query_tokens = self.tokenise(query)
        if not query_tokens:
            return []

        scores = [self._score_doc(query_tokens, i) for i in range(len(self.corpus))]
        ranked = sorted(
            [(scores[i], i) for i in range(len(scores)) if scores[i] >= min_score],
            key=lambda x: x[0],
            reverse=True,
        )

        results = []
        for score, idx in ranked[:top_k]:
            meta = self.metadata[idx]
            # Build a readable snippet (first 350 chars of the chunk text)
            full_text = " ".join(self.corpus[idx])  # reconstruct from tokens for brevity
            results.append({
                "score":      round(score, 3),
                "chunk_id":   meta.get("chunk_id", idx),
                "section":    meta.get("section", "Unknown"),
                "title":      meta.get("title", ""),
                "subsection": meta.get("subsection", ""),
                "pages":      meta.get("pages", []),
                "text":       meta.get("text", ""),          # full original text
                "snippet":    meta.get("text", "")[:350],    # for display
            })
        return results

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Serialise index to JSON."""
        data = {
            "k1":       self.k1,
            "b":        self.b,
            "corpus":   self.corpus,
            "metadata": self.metadata,
            "idf":      self.idf,
            "avgdl":    self.avgdl,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        print(f"[BM25] Index saved → {path}")

    def load(self, path: str) -> None:
        """Load a previously saved index from JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.k1       = data["k1"]
        self.b        = data["b"]
        self.corpus   = data["corpus"]
        self.metadata = data["metadata"]
        self.idf      = data["idf"]
        self.avgdl    = data["avgdl"]
        print(f"[BM25] Index loaded — {len(self.corpus):,} chunks")

    @property
    def is_empty(self) -> bool:
        return len(self.corpus) == 0

    # ── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def tokenise(text: str) -> List[str]:
        text = text.lower()
        tokens = re.findall(r'\b[a-z][a-z0-9\-]*\b', text)
        return [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]

    def _score_doc(self, query_tokens: List[str], doc_idx: int) -> float:
        doc   = self.corpus[doc_idx]
        tf    = Counter(doc)
        dl    = len(doc)
        score = 0.0
        for term in query_tokens:
            if term not in self.idf:
                continue
            f      = tf.get(term, 0)
            numer  = f * (self.k1 + 1)
            denom  = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            score += self.idf[term] * numer / denom
        return score
