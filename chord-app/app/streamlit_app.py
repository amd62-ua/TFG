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

st.title("🎵 Acordes + letra sincronizada")

lang = st.selectbox(
    "Idioma",
    #["auto", "es", "en"],
    ["es"],
    index=0
)

st.divider()

st.subheader(
    "🎲 Generador canciones aleatorias"
)

if st.button(
    "Generar canciones"
):

    txt_random = get_random_songs_txt()

    st.download_button(
        label="⬇️ Descargar canciones",
        data=txt_random,
        file_name="canciones_random.txt",
        mime="text/plain"
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