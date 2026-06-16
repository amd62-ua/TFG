import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
from utils.random_songs import (
    get_random_songs_txt
)



import streamlit as st
import tempfile
from core.detector import DetectChords
from core.audio import convert_to_wav
from faster_whisper import WhisperModel
import torch
import json
import csv
import io

@st.cache_resource
def load_whisper():
    if torch.cuda.is_available():
        return WhisperModel(
            "medium",
            device="cuda",
            compute_type="float16"
        )
    else:
        return WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

class ChordSegment:
    def __init__(self, start, end, chord):
        self.start = start
        self.end = end
        self.chord = chord

def transcribe_words(path, language=None):
    model = load_whisper()

    segments, _ = model.transcribe(
        path,
        language=language,
        word_timestamps=True
    )

    words = []

    for seg in segments:
        seg_text = seg.text.lower().strip()

        BLACKLIST = [
            "subtítulos realizados por la comunidad de amara.org",
            "amara.org"
        ]

        if any(
            bad in seg_text
            for bad in BLACKLIST
        ):
            continue
        for w in seg.words:
            words.append({
                "word": w.word.strip(),
                "start": float(w.start),
                "end": float(w.end),
            })

    return words

def find_chord(segs, t):
    for s in segs:
        if s.start <= t < s.end:
            return s.chord

    return segs[-1].chord if segs else "N"



def merge_words(words, segs):

    rows = []

    prev = None
    BLACKLIST = [
        "subtítulos realizados por la comunidad de amara.org",
        "amara.org",
    ]

    for w in words:

        chord = find_chord(
            segs,
            w["start"]
        )

        text = w["word"].strip()

        if any(
            bad in text.lower()
            for bad in BLACKLIST
        ):
            continue

        rows.append({
            "word": w["word"],
            "start": w["start"],
            "end": w["end"],
            "chord": chord,
            "show_chord": chord != prev
        })

        prev = chord

    return rows

def build_text(rows, segs, max_chars=42):

    out = []

    chord_line = ""
    lyric_line = ""

    rendered = set()
    last_rendered_chord = None

    # detectar gaps instrumentales
    instrumental_gaps = []

    for i in range(len(rows) - 1):

        gap_start = rows[i]["end"]
        gap_end = rows[i + 1]["start"]

        gap_duration = gap_end - gap_start

        # si hay más de 4 segundos sin voz
        if gap_duration > 4:

            instrumental_gaps.append({
                "start": gap_start,
                "end": gap_end
            })

    rendered_gaps = set()

    def build_instrumental_block(chords):

        line = "[Instrumental]\n"

        last = None

        for c in chords:

            if c.chord == "N":
                continue

            if c.chord != last:

                line += f"{c.chord}    "
                last = c.chord

        return line.strip()

    # =========================
    # INTRO instrumental
    # =========================

    if rows and segs:

        first_word_time = rows[0]["start"]

        intro_chords = [
            s for s in segs
            if (
                s.start < first_word_time
                and s.chord != "N"
            )
        ]

        if intro_chords:

            out.append(
                build_instrumental_block(
                    intro_chords
                )
            )

            out.append("")

    line_start = 0

    for r in rows:

        word = r["word"]

        start = r["start"]
        end = r["end"]

        # =========================
        # Instrumentales intermedios
        # =========================

        for gap in instrumental_gaps:

            key = (
                round(gap["start"], 2),
                round(gap["end"], 2)
            )

            if key in rendered_gaps:
                continue

            if start >= gap["end"]:

                instrumental_chords = [
                    s for s in segs
                    if (
                        s.start >= gap["start"]
                        and s.end <= gap["end"]
                        and s.chord != "N"
                    )
                ]

                if instrumental_chords:

                    # cerrar línea actual
                    if lyric_line:

                        out.append(chord_line.rstrip())
                        out.append(lyric_line.rstrip())
                        out.append("")

                        chord_line = ""
                        lyric_line = ""

                    out.append(
                        build_instrumental_block(
                            instrumental_chords
                        )
                    )

                    out.append("")

                    rendered_gaps.add(key)

        duration = max(end - start, 0.001)

        add = word + " "

        # salto de línea por pausa + mayúscula
        if lyric_line:

            prev_end = rows[rows.index(r) - 1]["end"]

            pause = start - prev_end

            if (
                pause > 1.2
                and word[:1].isupper()
            ):

                out.append(chord_line.rstrip())
                out.append(lyric_line.rstrip())
                out.append("")

                chord_line = ""
                lyric_line = ""

                #rendered = set()

        if len(lyric_line) + len(add) > max_chars:

            out.append(chord_line.rstrip())
            out.append(lyric_line.rstrip())
            out.append("")

            chord_line = ""
            lyric_line = ""

           # rendered = set()

            line_start = start

        cursor = len(lyric_line)

        lyric_line += add

        while len(chord_line) < len(lyric_line):
            chord_line += " "

        active_chords = []

        for s in segs:

            if (
                s.end >= start
                and s.start <= end
                and s.chord != "N"
            ):
                active_chords.append(s)

        for s in active_chords:

            chord = s.chord

            if chord == last_rendered_chord:
                continue

            key = (round(s.start, 2), chord)

            if key in rendered:
                continue

            ratio = (s.start - start) / duration

            ratio = max(0, min(ratio, 1))

            offset = int(ratio * len(word))

            pos = cursor + offset

            while len(chord_line) < pos + len(chord):
                chord_line += " "

            overlap = False

            for i in range(len(chord)):

                if (
                    pos + i < len(chord_line)
                    and chord_line[pos + i] != " "
                ):
                    overlap = True
                    break

            if overlap:
                pos += 2

            while len(chord_line) < pos:
                chord_line += " "

            while (
                pos < len(chord_line)
                and any(
                    c != " "
                    for c in chord_line[pos:pos + len(chord)]
                )
            ):
                pos += 1

            if pos >= len(chord_line):

                chord_line += " " * (
                    pos - len(chord_line)
                )

                chord_line += chord

            else:

                chord_line = (
                    chord_line[:pos]
                    + chord
                    + chord_line[pos:]
                )

            rendered.add(key)

            last_rendered_chord = chord

    # =========================
    # última línea
    # =========================

    if lyric_line:

        out.append(chord_line.rstrip())
        out.append(lyric_line.rstrip())

    return "\n".join(out)