import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st
import tempfile
from core.detector import DetectChords
from core.audio import convert_to_wav
from faster_whisper import WhisperModel
import torch

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

    for w in words:

        chord = find_chord(
            segs,
            w["start"]
        )

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

    line_start = 0

    for r in rows:

        word = r["word"]

        start = r["start"]
        end = r["end"]

        duration = max(end - start, 0.001)

        add = word + " "

        if len(lyric_line) + len(add) > max_chars:

            out.append(chord_line.rstrip())
            out.append(lyric_line.rstrip())
            out.append("")

            chord_line = ""
            lyric_line = ""

            rendered = set()

            line_start = start

        cursor = len(lyric_line)

        lyric_line += add

        while len(chord_line) < len(lyric_line):
            chord_line += " "

        for s in segs:

            if not (start <= s.start < end):
                continue

            chord = s.chord

            key = (round(s.start, 2), chord)

            if key in rendered:
                continue

            ratio = (s.start - start) / duration

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

            while len(chord_line) < pos + len(chord):
                chord_line += " "

            chord_line = (
                chord_line[:pos]
                + chord
                + chord_line[pos + len(chord):]
            )

            rendered.add(key)

    if lyric_line:

        out.append(chord_line.rstrip())
        out.append(lyric_line.rstrip())

    return "\n".join(out)

st.title("🎵 Acordes + letra sincronizada")

lang = st.selectbox(
    "Idioma",
    ["auto", "es", "en"],
    index=0
)

mode = st.radio(
    "Modo",
    [
        "Audio completo",
        "Voz + instrumental separados"
    ]
)

if mode == "Audio completo":

    uploaded = st.file_uploader(
        "Sube audio",
        type=["mp3", "wav"],
        key="full"
    )

    vocals_path = None
    instrumental_path = None

    if uploaded:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3"
        ) as tmp:

            tmp.write(uploaded.read())

            full_path = tmp.name

        st.audio(full_path)

        vocals_path = full_path
        instrumental_path = full_path

else:

    vocals = st.file_uploader(
        "Sube archivo de voz",
        type=["mp3", "wav"],
        key="vocals"
    )

    instrumental = st.file_uploader(
        "Sube instrumental",
        type=["mp3", "wav"],
        key="instr"
    )

    vocals_path = None
    instrumental_path = None

    if vocals:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3"
        ) as tmp:

            tmp.write(vocals.read())

            vocals_path = tmp.name

        st.audio(vocals_path)

    if instrumental:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3"
        ) as tmp:

            tmp.write(instrumental.read())

            instrumental_path = tmp.name

        st.audio(instrumental_path)

if vocals_path and instrumental_path:

    if st.button("Procesar"):

        with st.spinner("Procesando..."):

            vocals_wav = convert_to_wav(vocals_path)
            instrumental_wav = convert_to_wav(instrumental_path)

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
                None if lang == "auto" else lang
            )

            rows = merge_words(words, segs)

            txt = build_text(
                rows,
                segs,
                max_chars=48
            )

            st.success("Procesado!")

            st.subheader("🎤 Letra con acordes")

            st.markdown(f"```\n{txt}\n```")