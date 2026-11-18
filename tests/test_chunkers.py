"""Chunker tests — text strategies, code, structured, html, docx, pdf."""

from __future__ import annotations

import io

from app.services.chunking.base import (
    chunk_text_recursive,
    chunk_word_list,
    split_sentences,
)
from app.services.chunking.code_chunker import CodeChunker
from app.services.chunking.docx_chunker import DocxChunker
from app.services.chunking.html_chunker import HtmlChunker
from app.services.chunking.pdf_chunker import PdfChunker
from app.services.chunking.registry import ChunkerRegistry
from app.services.chunking.structured_chunker import StructuredChunker
from app.services.chunking.text_chunker import TextChunker
from tests.conftest import make_document, make_settings


def test_chunk_word_list_overlap():
    words = [f"w{i}" for i in range(10)]
    chunks = chunk_word_list(words, size=4, overlap=1)
    assert chunks[0] == "w0 w1 w2 w3"
    assert chunks[1] == "w3 w4 w5 w6"
    assert chunks[-1].endswith("w9")


def test_split_sentences():
    assert split_sentences("First sentence. Second one! Is this third? Yes.") == [
        "First sentence.",
        "Second one!",
        "Is this third?",
        "Yes.",
    ]


def test_recursive_chunker_respects_size(settings):
    text = "\n\n".join(f"Paragraph {i} " + "word " * 60 for i in range(5))
    chunks = chunk_text_recursive(text, size_words=50, overlap_words=10)
    assert len(chunks) >= 5
    for chunk in chunks:
        assert len(chunk.split()) <= 60  # size + overlap carry


def test_section_chunker_carries_heading(tmp_path):
    settings = make_settings(tmp_path, text_chunk_strategy="section")
    chunker = TextChunker(settings)
    doc = make_document("guide.md")
    text = (
        "# Getting started\n\nThis is the intro.\n\n"
        "# Retrieval\n\nDense search uses vectors. Sparse search uses BM25.\n\n"
        "# Reranking\n\nA cross-encoder scores pairs."
    )
    chunks = chunker.chunk(doc, text.encode())
    assert len(chunks) == 3
    assert chunks[1].text.startswith("Retrieval\n")
    assert "BM25" in chunks[1].text
    assert chunks[1].metadata["heading"] == "Retrieval"


def test_section_chunker_splits_long_section(tmp_path):
    settings = make_settings(tmp_path, text_chunk_strategy="section", section_max_words=20)
    chunker = TextChunker(settings)
    doc = make_document("long.md")
    body = " ".join(f"Sentence {i} here." for i in range(30))
    chunks = chunker.chunk(doc, f"# Big section\n\n{body}".encode())
    assert len(chunks) > 1
    assert all(c.text.startswith("Big section") for c in chunks)


def test_section_chunker_no_headings_falls_back(tmp_path):
    settings = make_settings(tmp_path, text_chunk_strategy="section")
    chunker = TextChunker(settings)
    doc = make_document("plain.txt")
    chunks = chunker.chunk(doc, b"Just plain text without any headings at all.")
    assert len(chunks) == 1


def test_fixed_chunker(tmp_path):
    settings = make_settings(
        tmp_path,
        text_chunk_strategy="fixed",
        chunk_size_words=10,
        chunk_overlap_words=2,
    )
    chunker = TextChunker(settings)
    doc = make_document("fixed.txt")
    text = " ".join(f"word{i}" for i in range(25))
    chunks = chunker.chunk(doc, text.encode())
    assert len(chunks) == 3
    assert chunks[0].text.startswith("word0")


def test_code_chunker_splits_functions(tmp_path):
    settings = make_settings(tmp_path)
    chunker = CodeChunker(settings)
    doc = make_document("example.py")
    code = (
        "def add(a, b):\n    return a + b\n\n\n"
        "def multiply(a, b):\n    return a * b\n\n\n"
        "class Calculator:\n    def divide(self, a, b):\n        return a / b\n"
    )
    chunks = chunker.chunk(doc, code.encode())
    assert len(chunks) == 3
    assert chunks[0].metadata["symbol"] == "add"
    assert chunks[2].metadata["symbol"] == "Calculator"
    assert chunks[2].metadata["kind"] == "class"


def test_code_chunker_falls_back_without_blocks(tmp_path):
    settings = make_settings(tmp_path)
    chunker = CodeChunker(settings)
    doc = make_document("notes.py")
    chunks = chunker.chunk(doc, b"x = 1\ny = 2\nprint(x + y)\n")
    assert len(chunks) == 1


def test_structured_csv(tmp_path):
    settings = make_settings(tmp_path)
    chunker = StructuredChunker(settings)
    doc = make_document("data.csv")
    csv_text = "name,role,team\nalice,engineer,search\nbob,designer,web\n"
    chunks = chunker.chunk(doc, csv_text.encode())
    assert len(chunks) == 2
    assert "name: alice" in chunks[0].text
    assert chunks[0].metadata["row"] == 1


def test_structured_json_list(tmp_path):
    settings = make_settings(tmp_path)
    chunker = StructuredChunker(settings)
    doc = make_document("data.json")
    chunks = chunker.chunk(doc, b'[{"a": 1, "b": 2}, {"a": 3, "b": 4}]')
    assert len(chunks) == 2
    assert "a: 1" in chunks[0].text


def test_html_chunker(tmp_path):
    settings = make_settings(tmp_path)
    chunker = HtmlChunker(settings)
    doc = make_document("page.html")
    html = (
        "<html><head><style>.x{}</style></head><body>"
        "<h1>Title</h1><p>First paragraph here.</p>"
        "<h2>Second</h2><p>Second paragraph here.</p>"
        "<script>var x = 1;</script></body></html>"
    )
    chunks = chunker.chunk(doc, html.encode())
    assert len(chunks) == 2
    assert "var x" not in chunks[0].text
    assert chunks[0].metadata["heading"] == "Title"


def test_docx_chunker(tmp_path):
    from docx import Document as DocxDocument

    settings = make_settings(tmp_path)
    chunker = DocxChunker(settings)
    doc = make_document("doc.docx")
    buf = io.BytesIO()
    d = DocxDocument()
    d.add_heading("Intro", level=1)
    d.add_paragraph("Hello world.")
    d.add_heading("Details", level=2)
    d.add_paragraph("More detail here.")
    d.save(buf)
    chunks = chunker.chunk(doc, buf.getvalue())
    assert len(chunks) == 2
    assert chunks[0].metadata["heading"] == "Intro"


def test_pdf_chunker(tmp_path):
    from pypdf import PdfWriter

    settings = make_settings(tmp_path)
    chunker = PdfChunker(settings)
    doc = make_document("doc.pdf")
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    chunks = chunker.chunk(doc, buf.getvalue())
    # Blank page has no text: zero chunks, no crash.
    assert chunks == []


def test_registry_dispatch_and_unknown(tmp_path):
    settings = make_settings(tmp_path)
    registry = ChunkerRegistry(settings)
    assert registry.is_supported("md")
    assert registry.is_supported("pdf")
    assert registry.is_supported("mp4")
    assert not registry.is_supported("xyz")
    from app.core.exceptions import UnsupportedFileTypeError

    try:
        registry.get("xyz")
    except UnsupportedFileTypeError as exc:
        assert "xyz" in str(exc)
    else:
        raise AssertionError("expected UnsupportedFileTypeError")
