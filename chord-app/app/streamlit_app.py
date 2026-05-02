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
        chord = find_chord(segs, w["start"])
        show = chord != prev
        rows.append({**w, "chord": chord, "show_chord": show})
        prev = chord

    return rows

def build_text(rows, gap=1.0, max_words=5):
    out, cl, ll = [], "", ""
    last, count = None, 0

    for r in rows:
        chord = r["chord"] if r["show_chord"] else ""
        width = max(len(r["word"]), len(chord)) + 1

        cl += chord.ljust(width)
        ll += r["word"].ljust(width)
        count += 1

        if (last and r["start"] - last >= gap) or count >= max_words:
            out += [cl.rstrip(), ll.rstrip(), ""]
            cl = ll = ""
            count = 0

        last = r["end"]

    if ll:
        out += [cl.rstrip(), ll.rstrip()]

    return "\n".join(out)

st.title("🎵 Acordes + letra sincronizada")

lang = st.selectbox("Idioma de la letra", ["auto", "es", "en"], index=0)

uploaded_file = st.file_uploader("Sube un audio", type=["mp3", "wav"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(uploaded_file.read())
        input_path = tmp.name

    st.audio(input_path)

    if st.button("Procesar"):
        with st.spinner("Procesando..."):
            wav_file = convert_to_wav(input_path)

            detector = DetectChords()
            detector.build_models()
            timeline = detector.predict(wav_file)

            segs = [
                ChordSegment(t["start"], t["end"], t["chord"])
                for t in timeline
            ]

            words = transcribe_words(
                wav_file,
                None if lang == "auto" else lang
            )

            rows = merge_words(words, segs)

            txt = build_text(rows)

            st.success("Procesado!")

            st.subheader("🎤 Letra con acordes")
            st.markdown(f"```\n{txt}\n```")
