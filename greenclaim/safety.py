"""Defenses against adversarial input: hidden text, prompt injection, made-up evidence."""

import re

import requests
from bs4 import BeautifulSoup, Comment

# Phrases that address the AI rather than a shopper. Matched per sentence.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (the |all |any )?(previous|prior|above|rules|instructions)",
    r"\b(you are|act as|pretend to be) (now )?(an? )?(ai|assistant|model|reviewer|auditor)",
    r"\b(system|developer) (prompt|message|instructions?)\b",
    r"\b(ai|llm|assistant|model|reviewer|auditor|agent)s?\b.{0,40}\b(must|should|will|shall)\b.{0,40}\b(rate|mark|classify|label|report|treat|consider|approve)",
    r"\b(rate|mark|classify|label|treat) (all|every|each|these|this|the) (claims?|statements?|product)\b.{0,30}\b(compliant|low[- ]risk|safe|approved|accurate)",
    r"\b(do not|don't|never) (flag|report|mention|question)\b",
    r"\bnew instructions?\b",
    r"\boverride\b",
]
_INJECTION_RE = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.IGNORECASE)

_HIDDEN_STYLE_RE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?![.\d]*[1-9])|"
    r"opacity\s*:\s*0(?![.\d]*[1-9])|(?:^|;)\s*color\s*:\s*(?:#fff(?:fff)?|white)\b|"
    r"left\s*:\s*-\d{3,}px|height\s*:\s*0(?:px)?\s*;.*overflow\s*:\s*hidden",
    re.IGNORECASE,
)


def fetch_url(url: str, timeout: int = 15) -> str:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 GreenClaimCheck"})
    resp.raise_for_status()
    return resp.text


def html_to_text(html: str, strip_hidden: bool = True) -> tuple[str, list[str]]:
    """Return the visible page text and a list of hidden text blocks that were removed."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    hidden: list[str] = []
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        if strip_hidden and c.strip():
            hidden.append(c.strip())
        c.extract()
    if strip_hidden:
        for tag in soup.find_all(True):
            if tag.decomposed:
                continue
            style = tag.get("style", "") or ""
            if (
                tag.has_attr("hidden")
                or tag.get("aria-hidden") == "true"
                or _HIDDEN_STYLE_RE.search(style)
            ):
                text = tag.get_text(" ", strip=True)
                if text:
                    hidden.append(text)
                tag.decompose()
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text), hidden


def redact_injections(text: str) -> tuple[str, list[str]]:
    """Replace instruction-like sentences with a marker. Returns new text and what was removed."""
    found: list[str] = []
    parts = re.split(r"(?<=[.!?\n])\s+", text)
    out = []
    for part in parts:
        if _INJECTION_RE.search(part):
            found.append(part.strip())
            out.append("[REMOVED: text addressed to the AI reviewer]")
        else:
            out.append(part)
    return " ".join(out), found


def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9%]+", " ", s).strip()


def quote_in_source(quote: str, source: str) -> bool:
    """True if the quote really appears in the source text (ignoring case and punctuation)."""
    q = _norm(quote)
    return bool(q) and q in _norm(source)
