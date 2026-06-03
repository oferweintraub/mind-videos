"""Extract plain text from a draft document.

Used by the /new-script slash command when the user supplies a draft instead
of a topic. Supports the formats people actually paste from:

    .txt  .md  .docx  .pdf

Usage:
    python scripts/extract_text.py path/to/file

Prints the extracted text to stdout. On unsupported format or read failure,
prints an error to stderr and exits 1.
"""

from __future__ import annotations

import sys
from pathlib import Path


def extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_docx(path: Path) -> str:
    try:
        import docx  # type: ignore
    except ImportError:
        sys.exit(
            "ERROR: python-docx not installed. Run: pip install python-docx\n"
            "(or `pip install -r requirements.txt` from the repo root.)"
        )
    doc = docx.Document(str(path))
    paras: list[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            paras.append(text)
    return "\n\n".join(paras)


def extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        sys.exit(
            "ERROR: pypdf not installed. Run: pip install pypdf\n"
            "(or `pip install -r requirements.txt` from the repo root.)"
        )
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


EXTRACTORS = {
    ".txt": extract_txt,
    ".md": extract_txt,
    ".markdown": extract_txt,
    ".docx": extract_docx,
    ".pdf": extract_pdf,
}


def extract(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in EXTRACTORS:
        sys.exit(
            f"ERROR: unsupported format '{ext}'. Supported: {sorted(EXTRACTORS.keys())}.\n"
            f"  - For .doc (old Word), open in Word and Save As .docx, then re-run.\n"
            f"  - For Google Docs, File → Download → .docx, then re-run.\n"
            f"  - For .rtf or .html, paste content into a .txt and re-run."
        )
    if not path.exists():
        sys.exit(f"ERROR: file not found: {path}")
    return EXTRACTORS[ext](path)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/extract_text.py <path/to/file>")
    path = Path(sys.argv[1]).expanduser().resolve()
    text = extract(path)
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
