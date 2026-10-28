"""Whitespace-tolerant verbatim quote matching (shared by evidence, rules, summaries).

PDF text extraction puts line breaks and runs of spaces in the middle of
sentences, so a model that quotes a sentence on one line fails a strict
`quote in text` test even though every word is the source's. These helpers
compare after collapsing whitespace and unifying typographic quotes/dashes, but
they always return the *actual substring of the source*, so whatever is stored
is still verbatim source text and still passes any later `quote in text` check.
"""
import re
from typing import Optional

_PUNCT = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u00a0": " ", "\u200b": "", "\u00ad": "",
}


def _fold(ch: str) -> str:
    return _PUNCT.get(ch, ch)


def norm_ws(text: Optional[str]) -> str:
    """Lowercase-free normal form: unified punctuation, single spaces, trimmed."""
    if not text:
        return ""
    out = "".join(_fold(c) for c in str(text))
    out = re.sub(r"\s+", " ", out).strip()
    # A hyphen at a line break ("Merit-cum-\nMeans") reads the same as "Merit-cum-Means".
    return re.sub(r"- ", "-", out)


def find_verbatim(quote: Optional[str], text: Optional[str]) -> Optional[str]:
    """Return the exact substring of `text` that `quote` refers to, or None.

    Matching ignores whitespace layout and typographic quote/dash variants only.
    Words and their order must match exactly (case-sensitive).
    """
    if not quote or not text or not quote.strip():
        return None
    q = norm_ws(quote)
    if not q:
        return None

    # Fast path: already an exact substring.
    stripped = quote.strip()
    if stripped in text:
        return stripped

    # Build normalised text with a map from normalised index -> original index.
    norm_chars, index_map = [], []
    prev_space = True  # also trims leading whitespace
    for i, ch in enumerate(text):
        f = _fold(ch)
        if f == "":
            continue
        if f.isspace():
            if prev_space or (norm_chars and norm_chars[-1] == "-"):
                continue
            norm_chars.append(" ")
            index_map.append(i)
            prev_space = True
        else:
            norm_chars.append(f)
            index_map.append(i)
            prev_space = False
    norm_text = "".join(norm_chars)

    pos = norm_text.find(q)
    if pos < 0:
        return None
    start = index_map[pos]
    end = index_map[pos + len(q) - 1] + 1
    return text[start:end]
