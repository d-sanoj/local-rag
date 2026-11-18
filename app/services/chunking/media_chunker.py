"""Video/audio chunker (.mp4, .mov, .mkv, .mp3, .wav, .m4a, .webm, .ogg).

Transcribes with faster-whisper, then chunks the transcript into
timestamped segments (roughly ``media_segment_seconds`` each, split at
sentence boundaries). Each chunk carries its start/end time in seconds.
"""

from __future__ import annotations

import os
import tempfile

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking.base import BaseChunker, split_sentences

_SEGMENT_SPLIT_RE = None


class MediaChunker(BaseChunker):
    extensions = ("mp4", "mov", "mkv", "webm", "mp3", "wav", "m4a", "ogg", "flac")

    def __init__(self, settings: Settings):
        self.settings = settings

    def chunk(self, document: Document, content: bytes) -> list[Chunk]:
        from faster_whisper import WhisperModel

        suffix = f".{document.file_type}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            model = WhisperModel(self.settings.whisper_model, device="cpu", compute_type="int8")
            segments, _info = model.transcribe(tmp_path, beam_size=5)
            # Collect (start, end, text) per whisper segment.
            pieces: list[tuple[float, float, str]] = [
                (seg.start, seg.end, seg.text.strip()) for seg in segments if seg.text.strip()
            ]
        finally:
            os.unlink(tmp_path)
        if not pieces:
            return self._make_chunks(
                document,
                [f"[Audio/video: {document.path} — transcription produced no text.]"],
                [{"start_sec": 0.0, "end_sec": 0.0}],
            )
        return self._segment(document, pieces)

    def _segment(self, document: Document, pieces: list[tuple[float, float, str]]) -> list[Chunk]:
        target = self.settings.media_segment_seconds
        texts: list[str] = []
        metadatas: list[dict] = []
        current: list[str] = []
        start = pieces[0][0]
        end = pieces[0][1]
        for seg_start, seg_end, seg_text in pieces:
            for sentence in split_sentences(seg_text):
                if not sentence.strip():
                    continue
                # Close the current segment once it spans the target duration.
                if current and (seg_end - start) >= target:
                    texts.append(" ".join(current))
                    metadatas.append({"start_sec": round(start, 1), "end_sec": round(end, 1)})
                    current, start = [], seg_start
                current.append(sentence)
                end = seg_end
        if current:
            texts.append(" ".join(current))
            metadatas.append({"start_sec": round(start, 1), "end_sec": round(end, 1)})
        return self._make_chunks(document, texts, metadatas)
