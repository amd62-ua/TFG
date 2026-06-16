from core.audio import convert_to_wav
from core.detector import DetectChords

from core.transcription import transcribe_words
from core.chords import (
    ChordSegment,
    merge_words
)
from core.formatter import build_text


def process_song(
    vocals_path,
    instrumental_path,
    language="es"
):
    vocals_wav = convert_to_wav(
        vocals_path
    )

    instrumental_wav = convert_to_wav(
        instrumental_path
    )

    detector = DetectChords()

    detector.build_models()

    timeline = detector.predict(
        instrumental_wav
    )

    segs = [
        ChordSegment(
            t["start"],
            t["end"],
            t["chord"]
        )
        for t in timeline
    ]

    words = transcribe_words(
        vocals_wav,
        language
    )

    rows = merge_words(
        words,
        segs
    )

    txt = build_text(
        rows,
        segs,
        max_chars=64
    )

    return txt, timeline, rows