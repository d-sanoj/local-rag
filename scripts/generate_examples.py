#!/usr/bin/env python3
"""Generate the example documents for the CI end-to-end check.

Writes a small, fixed set of documents into ``data/examples/`` — one per
supported file type, each about a DIFFERENT topic with distinctive
vocabulary, so retrieval can be checked per file. The generated files are
committed to the repo; this script is how they are regenerated (and how CI
could rebuild them from scratch).

Binary files (pdf, docx, png, wav, mp4) are generated here too, so the
repo never carries an opaque blob nobody can reproduce.

Audio/video note: there is no speech synthesis on a CI runner, so the
media examples are a tone (wav) and a test-pattern clip (mp4). They exist
to exercise the transcription pipeline end to end (whisper loads, runs,
indexes a chunk), not to test retrieval of spoken words — the smoke test
only asserts they are indexed, never that a question retrieves them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "data" / "examples"

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# ---------------------------------------------------------------- text files

BEEKEEPING_MD = """# A beginner's guide to beekeeping

## Inspecting the hive

Inspect a beehive on a warm, calm day, ideally between late morning and
early afternoon when most forager bees are out. Open the hive slowly and
work from the outside frames inward. Look for the queen, check the brood
pattern, and watch for signs of varroa mites on the bees.

## The smoker

The smoker is the beekeeper's most important tool. A few gentle puffs of
cool smoke at the entrance and under the lid calm the colony: the smoke
masks the alarm pheromone, so the bees become docile instead of defensive.
Use dry fuel such as pine needles or wood shavings, and never use hot
smoke — it harms the bees and the wax.

## Feeding the colony

In the first year, feed a new colony sugar syrup (one part sugar to one
part water) until it has drawn out its brood frames. Stop feeding once the
bees are bringing in nectar on their own, and leave enough honey in the
hive for the winter.
"""

ORBITAL_TXT = """Orbital mechanics notes

A Hohmann transfer is the most fuel-efficient way to move a spacecraft
between two circular orbits in the same plane. The spacecraft fires its
engine once to enter an elliptical transfer orbit whose perigee touches
the inner orbit and whose apogee touches the outer orbit, coasts halfway
around, then fires again to circularise at the target altitude.

The total delta-v of a Hohmann transfer depends on the two orbital radii.
For a transfer from low Earth orbit at 300 kilometres up to geostationary
orbit, the total is about 3.9 kilometres per second, split into two burns
of roughly 2.4 and 1.5 kilometres per second.

Perigee is the point of an orbit closest to the body being orbited, and
apogee is the farthest point. A spacecraft moves fastest at perigee and
slowest at apogee, which is why the transfer burns happen at those two
points.
"""

LIBRARY_PY = '''"""A tiny library catalogue.

It exists so the code chunker has function and class boundaries to split
on, and so retrieval can be checked against code rather than prose.
"""


class LibraryCatalogue:
    """Holds the books a small branch library owns."""

    def __init__(self):
        self.books = {}

    def add_book(self, isbn, title, author):
        """Register a book by its ISBN."""
        self.books[isbn] = {"title": title, "author": author, "on_loan": False}

    def find_book_by_isbn(self, isbn):
        """Look a book up by ISBN. Returns the record, or None."""
        return self.books.get(isbn)


def overdue_fine(days_late, rate_per_day=0.25):
    """Compute the overdue fine for a late return.

    Fines are charged per day late, capped at the price of the book.
    A book returned on time has no fine at all.
    """
    if days_late <= 0:
        return 0.0
    return round(days_late * rate_per_day, 2)


def is_available(catalogue, isbn):
    """True when the book exists and is not currently on loan."""
    book = catalogue.find_book_by_isbn(isbn)
    return book is not None and not book["on_loan"]
'''

TRAIN_HTML = """<!DOCTYPE html>
<html>
<head><title>InterCity timetable — Friday departures</title></head>
<body>
<h1>InterCity timetable — Friday departures</h1>
<p>All trains leave from the main station. Times are in local time.</p>
<h2>Evening sleeper service</h2>
<p>The InterCity sleeper service to the north coast departs at 21:40 from
platform 7. It calls at three stations overnight and arrives at 07:15 the
next morning. Sleeping berths must be booked in advance, and the dining
car serves breakfast from 06:30.</p>
<h2>Daytime departures</h2>
<p>Daytime InterCity trains to the capital leave every hour from platform
3, the first at 06:05 and the last at 19:05. The journey takes two hours
and ten minutes with no changes.</p>
</body>
</html>
"""

BIRDWATCHING_CSV = """species,count,location,date
goldfinch,14,reservoir,2026-05-02
chaffinch,9,reservoir,2026-05-02
goldfinch,6,woodland edge,2026-05-03
kingfisher,2,river bend,2026-05-04
nuthatch,3,woodland edge,2026-05-04
"""

RECIPES_JSON = [
    {
        "name": "lemon drizzle cake",
        "servings": 8,
        "baking_time_minutes": 45,
        "ingredients": ["flour", "butter", "sugar", "eggs", "lemons"],
        "method": "Cream the butter and sugar, beat in the eggs, fold in the "
        "flour, bake at 180C, then pour the lemon syrup over the warm cake.",
    },
    {
        "name": "tomato soup",
        "servings": 4,
        "baking_time_minutes": 0,
        "ingredients": ["tomatoes", "onion", "garlic", "vegetable stock", "basil"],
        "method": "Soften the onion and garlic, add the tomatoes and stock, "
        "simmer for twenty minutes, then blend until smooth.",
    },
]

QUESTIONS = [
    {
        "file": "beekeeping-guide.md",
        "type": "md",
        "topic": "beekeeping — hive inspection and the smoker",
        "question": "How do I inspect a beehive and what does the smoker do?",
        "retrieval": True,
    },
    {
        "file": "orbital-mechanics-notes.txt",
        "type": "txt",
        "topic": "orbital mechanics — Hohmann transfer and delta-v",
        "question": "What is a Hohmann transfer and how much delta-v does it need?",
        "retrieval": True,
    },
    {
        "file": "library-catalogue.py",
        "type": "py",
        "topic": "code — library catalogue, find by ISBN, overdue fines",
        "question": "How does the library catalogue find a book by ISBN?",
        "retrieval": True,
    },
    {
        "file": "sourdough-guide.pdf",
        "type": "pdf",
        "topic": "sourdough baking — starter, levain, autolyse",
        "question": "How do I maintain a sourdough starter and what is autolyse?",
        "retrieval": True,
    },
    {
        "file": "telescope-report.docx",
        "type": "docx",
        "topic": "telescope observation — Andromeda nebula, aperture",
        "question": "What did the telescope observation report say about the Andromeda nebula?",
        "retrieval": True,
    },
    {
        "file": "train-timetable.html",
        "type": "html",
        "topic": "train timetable — InterCity sleeper service, platform 7",
        "question": "When does the InterCity sleeper service depart and from which platform?",
        "retrieval": True,
    },
    {
        "file": "birdwatching-sightings.csv",
        "type": "csv",
        "topic": "birdwatching — goldfinch count at the reservoir",
        "question": "What is the goldfinch count at the reservoir?",
        "retrieval": True,
    },
    {
        "file": "recipes.json",
        "type": "json",
        "topic": "recipes — lemon drizzle cake ingredients and baking time",
        "question": "What are the ingredients and baking time for the lemon drizzle cake?",
        "retrieval": True,
    },
    {
        "file": "zebra-crossing-sign.png",
        "type": "png",
        "topic": "image OCR — zebra crossing sign text",
        "question": "What does the zebra crossing sign say?",
        "retrieval": True,
        # Only asserted when the run passes --expect-ocr (CI installs
        # tesseract). Without OCR the image still indexes, but there is no
        # text to retrieve, so the retrieval check is skipped, not faked.
        "requires": "ocr",
    },
    {
        "file": "tone-sample.wav",
        "type": "wav",
        "topic": "audio — 3s tone (transcription pipeline only, no spoken words)",
        "question": None,
        "retrieval": False,
        "note": "Tone, not speech: only asserts the file is indexed.",
    },
    {
        "file": "test-pattern-clip.mp4",
        "type": "mp4",
        "topic": "video — 3s test pattern with tone (transcription pipeline only)",
        "question": None,
        "retrieval": False,
        "note": "Test pattern, not speech: only asserts the file is indexed.",
    },
]


def _write_text(name: str, content: str) -> None:
    (EXAMPLES_DIR / name).write_text(content, encoding="utf-8")


def _write_questions() -> None:
    # NOTE: the questions live in scripts/, NOT in data/examples/. They are
    # test configuration, not example documents — if they sat in the
    # documents folder they would be indexed themselves, and a search would
    # return the question text instead of the document that answers it.
    path = REPO_ROOT / "scripts" / "smoke_questions.json"
    path.write_text(json.dumps({"version": 1, "examples": QUESTIONS}, indent=2), encoding="utf-8")


def _make_pdf() -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    story = [
        Paragraph("A short guide to sourdough", styles["Title"]),
        Spacer(1, 12),
        Paragraph(
            "Keeping a sourdough starter alive is mostly about routine. "
            "Feed it once a day with equal weights of flour and water, keep "
            "it at room temperature, and discard half before each feeding so "
            "the yeast and bacteria stay in balance. A healthy starter "
            "doubles in size within a few hours of feeding and smells "
            "pleasantly tangy.",
            styles["Normal"],
        ),
        Spacer(1, 12),
        Paragraph(
            "Autolyse is the quiet first step of the dough. Mix just the "
            "flour and water and leave them alone for thirty to sixty "
            "minutes before adding the starter and salt. During the autolyse "
            "the flour hydrates fully and gluten starts to form on its own, "
            "which makes the dough easier to shape and gives the finished "
            "loaf a more open crumb.",
            styles["Normal"],
        ),
        Spacer(1, 12),
        Paragraph(
            "Bake the loaf in a hot Dutch oven so the steam stays trapped "
            "around it. That steam is what gives sourdough its crackling "
            "crust and its open, airy crumb.",
            styles["Normal"],
        ),
    ]
    SimpleDocTemplate(str(EXAMPLES_DIR / "sourdough-guide.pdf"), pagesize=A4).build(story)


def _make_docx() -> None:
    from docx import Document

    doc = Document()
    doc.add_heading("Telescope observation report — 12 April 2026", level=1)
    doc.add_paragraph(
        "Location: the hilltop observatory. Instrument: a 200mm reflector "
        "with a 25mm eyepiece, giving a wide field of view suited to "
        "extended objects."
    )
    doc.add_heading("Andromeda nebula", level=2)
    doc.add_paragraph(
        "The Andromeda nebula (M31) was the main target of the evening. "
        "Through the 200mm aperture its bright core was obvious, and with "
        "averted vision the faint outer disc stretched across a large part "
        "of the field. The companion galaxies M32 and M110 were both "
        "visible as small smudges near the core. The large aperture is what "
        "makes the difference here: the same object in a small telescope "
        "shows only the core."
    )
    doc.add_heading("Conditions", level=2)
    doc.add_paragraph(
        "Clear skies, steady seeing, no moon. The eyepiece gave a "
        "comfortable view for the whole session."
    )
    doc.save(str(EXAMPLES_DIR / "telescope-report.docx"))


def _make_png() -> None:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(FONT, 64)
    small = ImageFont.truetype(FONT, 40)
    img = Image.new("RGB", (1200, 420), "white")
    draw = ImageDraw.Draw(img)
    draw.text((60, 60), "ZEBRA CROSSING", fill="black", font=font)
    draw.text((60, 180), "PEDESTRIANS HAVE PRIORITY", fill="black", font=small)
    draw.text((60, 300), "LOOK BOTH WAYS", fill="black", font=small)
    img.save(str(EXAMPLES_DIR / "zebra-crossing-sign.png"))


def _run(cmd: list[str], label: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAILED to make {label}:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


def _make_media() -> None:
    wav = str(EXAMPLES_DIR / "tone-sample.wav")
    _run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3",
            "-ar",
            "16000",
            wav,
        ],
        "tone-sample.wav",
    )
    mp4 = str(EXAMPLES_DIR / "test-pattern-clip.mp4")
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=3:size=640x360:rate=15",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            mp4,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # No libx264 on this machine — fall back to the built-in mpeg4 encoder.
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=3:size=640x360:rate=15",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=3",
                "-shortest",
                "-c:v",
                "mpeg4",
                "-c:a",
                "aac",
                mp4,
            ],
            "test-pattern-clip.mp4",
        )


def main() -> None:
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    _write_text("beekeeping-guide.md", BEEKEEPING_MD)
    _write_text("orbital-mechanics-notes.txt", ORBITAL_TXT)
    _write_text("library-catalogue.py", LIBRARY_PY)
    _write_text("train-timetable.html", TRAIN_HTML)
    _write_text("birdwatching-sightings.csv", BIRDWATCHING_CSV)
    (EXAMPLES_DIR / "recipes.json").write_text(json.dumps(RECIPES_JSON, indent=2), encoding="utf-8")
    _make_pdf()
    _make_docx()
    _make_png()
    _make_media()
    _write_questions()
    for entry in QUESTIONS:
        print(f"  {entry['file']}  ({entry['type']}) — {entry['topic']}")
    print(f"Wrote {len(QUESTIONS)} example files to {EXAMPLES_DIR}")


if __name__ == "__main__":
    main()
