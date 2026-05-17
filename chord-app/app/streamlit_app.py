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
    last_rendered_chord = None

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

        active_chords = []

        for s in segs:

            if s.end >= start and s.start <= end:
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

            # asegurar longitud
            while len(chord_line) < pos:
                chord_line += " "

            # si hay overlap, mover a la derecha
            while (
                pos < len(chord_line)
                and any(
                    c != " "
                    for c in chord_line[pos:pos + len(chord)]
                )
            ):
                pos += 1

            # insertar acorde sin borrar
            if pos >= len(chord_line):

                chord_line += " " * (pos - len(chord_line))
                chord_line += chord

            else:

                chord_line = (
                    chord_line[:pos]
                    + chord
                    + chord_line[pos:]
                )

            rendered.add(key)

            last_rendered_chord = chord

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

if "processed" not in st.session_state:
    st.session_state.processed = False

if vocals_path and instrumental_path:

    if st.button("Procesar"):

        st.session_state.processed = False

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
                max_chars=64
            )

            st.session_state.txt = txt
            st.session_state.timeline = timeline
            st.session_state.rows = rows
            st.session_state.processed = True

if st.session_state.processed:

    txt = st.session_state.txt
    timeline = st.session_state.timeline
    rows = st.session_state.rows

    st.success("Procesado!")

    st.subheader("🎤 Letra con acordes")

    st.markdown(f"```\n{txt}\n```")

    # TXT letra + acordes
    st.download_button(
        label="⬇️ Descargar letra + acordes",
        data=txt,
        file_name="letra_acordes.txt",
        mime="text/plain"
    )

                # JSON timeline acordes
    timeline_json = json.dumps(
        timeline,
        ensure_ascii=False,
        indent=2
    )

    st.download_button(
        label="⬇️ Descargar timeline acordes JSON",
        data=timeline_json,
        file_name="timeline_acordes.json",
        mime="application/json"
    )

                # CSV timeline acordes
    csv_buffer = io.StringIO()

    writer = csv.writer(csv_buffer)

    writer.writerow([
        "start",
        "end",
        "chord"
    ])

    for t in timeline:

        writer.writerow([
            t["start"],
            t["end"],
            t["chord"]
        ])

    st.download_button(
        label="⬇️ Descargar timeline acordes CSV",
        data=csv_buffer.getvalue(),
        file_name="timeline_acordes.csv",
        mime="text/csv"
    )

                # Timeline letra
    lyrics_timeline = []

    for r in rows:

        lyrics_timeline.append({
            "word": r["word"],
            "start": r["start"],
            "end": r["end"]
        })

                # JSON letra
    lyrics_json = json.dumps(
        lyrics_timeline,
        ensure_ascii=False,
        indent=2
    )

    st.download_button(
        label="⬇️ Descargar timeline letra JSON",
        data=lyrics_json,
        file_name="timeline_letra.json",
        mime="application/json"
    )

                # CSV letra
    lyrics_csv = io.StringIO()

    writer = csv.writer(lyrics_csv)

    writer.writerow([
        "word",
        "start",
        "end"
    ])

    for w in lyrics_timeline:

        writer.writerow([
            w["word"],
            w["start"],
            w["end"]
        ])

    st.download_button(
        label="⬇️ Descargar timeline letra CSV",
        data=lyrics_csv.getvalue(),
        file_name="timeline_letra.csv",
        mime="text/csv"
    )