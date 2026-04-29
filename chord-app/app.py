from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

import altair as alt
import librosa
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Acordes + letra sincronizada", layout="wide")

PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class ChordSegment:
    start: float
    end: float
    chord: str
    confidence: float


# ------------------ AUDIO ------------------

@st.cache_data(show_spinner=False)
def load_audio(file_bytes: bytes, filename: str, sr: int = 22050):
    suffix = os.path.splitext(filename)[1] or ".audio"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(file_bytes)
        tmp.close()
        y, sr = librosa.load(tmp.name, sr=sr, mono=True)
        return y, sr
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def save_temp_audio(file_bytes: bytes, filename: str) -> str:
    suffix = os.path.splitext(filename)[1] or ".audio"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(file_bytes)
    tmp.close()
    return tmp.name


def cleanup_temp_file(path: str):
    if path and os.path.exists(path):
        os.unlink(path)


# ------------------ AUTO PARÁMETROS ------------------

def auto_params(y, sr):
    y_harmonic, _ = librosa.effects.hpss(y)
    tempo, _ = librosa.beat.beat_track(y=y_harmonic, sr=sr)

    tempo = float(np.asarray(tempo).squeeze())

    if tempo >= 140:
        return 1024, 2, tempo
    elif tempo >= 90:
        return 2048, 3, tempo
    else:
        return 4096, 4, tempo


# ------------------ ACORDES ------------------

def build_chord_templates():
    templates = []
    names = []

    chord_defs = {
        "": [0, 4, 7],
        "m": [0, 3, 7],
        "7": [0, 4, 7, 10],
        "maj7": [0, 4, 7, 11],
        "m7": [0, 3, 7, 10],
        "sus4": [0, 5, 7],
        "sus2": [0, 2, 7],
    }

    for quality, intervals in chord_defs.items():
        base = np.zeros(12)
        base[intervals] = 1

        for i, root in enumerate(PITCH_CLASSES):
            templates.append(np.roll(base, i))
            names.append(root + quality)

    templates = np.array(templates)
    templates /= np.linalg.norm(templates, axis=1, keepdims=True) + 1e-8

    return templates, names


def simplify_chord_name(chord):
    for suffix in ["maj7", "m7", "sus4", "sus2", "7"]:
        if chord.endswith(suffix):
            return chord[:-len(suffix)]
    return chord


def smooth_labels(labels, min_frames=3):
    smoothed = labels[:]
    start = 0

    while start < len(labels):
        end = start + 1
        while end < len(labels) and labels[end] == labels[start]:
            end += 1

        if end - start < min_frames:
            left = smoothed[start - 1] if start > 0 else None
            right = labels[end] if end < len(labels) else None
            replacement = left or right or labels[start]

            for i in range(start, end):
                smoothed[i] = replacement

        start = end

    return smoothed


def merge_segments(labels, confidences, times):
    segments = []
    start_idx = 0

    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start_idx]:
            end_time = times[i] if i < len(times) else times[-1]
            segments.append(
                ChordSegment(
                    float(times[start_idx]),
                    float(end_time),
                    labels[start_idx],
                    float(np.mean(confidences[start_idx:i])),
                )
            )
            start_idx = i

    return segments


def detect_chords(y, sr, hop_length=2048, smoothing_frames=3):
    templates, names = build_chord_templates()

    y_harmonic, _ = librosa.effects.hpss(y)

    chroma = librosa.feature.chroma_cqt(
        y=y_harmonic,
        sr=sr,
        hop_length=hop_length,
        bins_per_octave=36,
    )
    chroma = librosa.util.normalize(chroma, axis=0)

    tempo, beats = librosa.beat.beat_track(
        y=y_harmonic,
        sr=sr,
        hop_length=hop_length,
    )

    duration = librosa.get_duration(y=y, sr=sr)

    if len(beats) >= 4:
        beat_chroma = librosa.util.sync(chroma, beats, aggregate=np.median)

        beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=hop_length)

        if beat_chroma.shape[1] + 1 == len(beat_times):
            times = np.append(beat_times, duration)
        else:
            times = np.linspace(0, duration, beat_chroma.shape[1] + 1)

        chroma_used = beat_chroma
    else:
        chroma_used = chroma
        times = librosa.frames_to_time(
            np.arange(chroma_used.shape[1] + 1),
            sr=sr,
            hop_length=hop_length,
        )

    scores = templates @ chroma_used
    best_idx = np.argmax(scores, axis=0)
    best_scores = scores[best_idx, np.arange(scores.shape[1])]

    labels = [simplify_chord_name(names[i]) for i in best_idx]
    labels = smooth_labels(labels, smoothing_frames)

    segments = merge_segments(labels, best_scores.tolist(), times)

    df = pd.DataFrame([
        {
            "inicio": round(s.start, 2),
            "fin": round(s.end, 2),
            "duracion": round(s.end - s.start, 2),
            "acorde": s.chord,
            "confianza": round(s.confidence, 3),
        }
        for s in segments
    ])

    return segments, df, chroma


def merge_resolutions(df_fast, df_slow):
    merged = []

    for _, slow in df_slow.iterrows():
        slow = slow.copy()

        fast_matches = df_fast[
            (df_fast["inicio"] >= slow["inicio"]) &
            (df_fast["fin"] <= slow["fin"])
        ]

        if len(fast_matches) == 0:
            merged.append(slow)
            continue

        counts = fast_matches["acorde"].value_counts()
        best_fast = counts.idxmax()

        if counts.max() >= 2:
            slow["acorde"] = best_fast
            slow["confianza"] = round(float(fast_matches["confianza"].mean()), 3)

        merged.append(slow)

    return pd.DataFrame(merged).reset_index(drop=True)


# ------------------ TONALIDAD ------------------

def estimate_key_krumhansl(chroma):
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    chroma_mean = np.mean(chroma, axis=1)

    scores = []
    for i in range(12):
        scores.append((np.corrcoef(np.roll(major_profile, i), chroma_mean)[0, 1], PITCH_CLASSES[i]))
        scores.append((np.corrcoef(np.roll(minor_profile, i), chroma_mean)[0, 1], PITCH_CLASSES[i] + "m"))

    return max(scores, key=lambda x: x[0])[1]


def chord_root(chord):
    if not chord:
        return None

    for note in sorted(PITCH_CLASSES, key=len, reverse=True):
        if chord.startswith(note):
            return note

    return None


def normalize_key(key, df):
    if df.empty:
        return key

    counts = df["acorde"].value_counts()
    top_chords = counts.head(6).index.tolist()
    top_roots = [chord_root(c) for c in top_chords]
    top_roots = [r for r in top_roots if r in PITCH_CLASSES]

    root = chord_root(key)
    if root not in PITCH_CLASSES:
        return top_roots[0] if top_roots else key

    # Si Krumhansl detecta V, bajar quinta: C# -> F#
    possible_i_from_v = PITCH_CLASSES[(PITCH_CLASSES.index(root) - 7) % 12]
    if possible_i_from_v in top_roots:
        return possible_i_from_v

    # Si detecta IV, bajar cuarta: D# -> A#
    possible_i_from_iv = PITCH_CLASSES[(PITCH_CLASSES.index(root) - 5) % 12]
    if possible_i_from_iv in top_roots:
        return possible_i_from_iv

    if root not in top_roots and top_roots:
        return top_roots[0]

    return key


def diatonic_chords(key):
    major_scale = [0, 2, 4, 5, 7, 9, 11]
    minor_scale = [0, 2, 3, 5, 7, 8, 10]

    root = key.replace("m", "")
    if root not in PITCH_CLASSES:
        return set()

    is_minor = key.endswith("m")
    scale = minor_scale if is_minor else major_scale
    idx = PITCH_CLASSES.index(root)

    notes = [PITCH_CLASSES[(idx + i) % 12] for i in scale]

    if is_minor:
        qualities = ["m", "", "", "m", "m", "", ""]
    else:
        qualities = ["", "m", "m", "", "", "m", ""]

    return {n + q for n, q in zip(notes, qualities)}


def snap_to_scale(chord, key):
    valid = diatonic_chords(key)

    if not chord or chord == "N" or not valid:
        return chord

    if chord in valid:
        return chord

    root = chord_root(chord)
    if root not in PITCH_CLASSES:
        return chord

    idx = PITCH_CLASSES.index(root)

    best = None
    best_dist = 999

    for v in valid:
        v_root = chord_root(v)
        if v_root not in PITCH_CLASSES:
            continue

        dist = abs(PITCH_CLASSES.index(v_root) - idx)
        dist = min(dist, 12 - dist)

        if dist < best_dist:
            best = v
            best_dist = dist

    return best if best else chord


def fix_chord_quality(chord, key):
    valid = diatonic_chords(key)

    if chord in valid:
        return chord

    root = chord_root(chord)
    if root is None:
        return chord

    for v in valid:
        if chord_root(v) == root:
            return v

    return chord


# ------------------ TRANSPOSICIÓN ------------------

def transpose_chord(chord, shift):
    root = chord_root(chord)
    if root is None:
        return chord

    idx = PITCH_CLASSES.index(root)
    new_root = PITCH_CLASSES[(idx + shift) % 12]
    return new_root + chord[len(root):]


def transpose_all(df, segments, shift):
    df = df.copy()
    df["acorde"] = df["acorde"].apply(lambda c: transpose_chord(c, shift))

    new_segments = [
        ChordSegment(s.start, s.end, transpose_chord(s.chord, shift), s.confidence)
        for s in segments
    ]

    return df, new_segments


# ------------------ WHISPER ------------------

def transcribe_words(path, model="base", language=None):
    import whisper

    m = whisper.load_model(model)

    kwargs = {
        "word_timestamps": True,
        "fp16": False,
        "task": "transcribe",
    }

    if language:
        kwargs["language"] = language

    result = m.transcribe(path, **kwargs)

    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": float(w["start"]),
                "end": float(w["end"]),
            })

    return words


# ------------------ LETRA ------------------

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

    return pd.DataFrame(rows)


def build_text(df, gap=1.0, max_words=5):
    out, cl, ll = [], "", ""
    last, count = None, 0

    for _, r in df.iterrows():
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


# ------------------ UI ------------------

st.title("🎵 Acordes + letra sincronizada")

with st.sidebar:
    sr = st.selectbox("SR", [22050, 44100], index=0)

    auto_mode = st.checkbox("Auto parámetros", True)

    manual_hop = st.selectbox("Resolución manual", [1024, 2048, 4096], index=1)
    manual_smooth = st.slider("Suavizado manual", 1, 10, 3)

    lang = st.selectbox("Idioma", ["auto", "es", "en"], index=0)

    use_key_correction = st.checkbox("Corregir acordes según tonalidad", False)

    transpose = st.checkbox("Transponer")
    target_key = st.selectbox("Nueva tonalidad", PITCH_CLASSES, index=7)

    gap = st.slider("Silencio", 0.4, 2.0, 1.0)
    max_words = st.slider("Palabras por línea", 3, 10, 5)

file = st.file_uploader("Audio")

if file:
    data = file.read()
    st.audio(data)

    y, sr = load_audio(data, file.name, sr)

    if auto_mode:
        hop, smooth, tempo = auto_params(y, sr)
    else:
        hop, smooth = manual_hop, manual_smooth
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.asarray(tempo).squeeze())

    st.info(f"Tempo estimado: {tempo:.1f} BPM · hop={hop} · suavizado={smooth}")

    fast_hop = max(512, hop // 2)
    slow_hop = hop

    _, df_fast, chroma = detect_chords(y, sr, fast_hop, smooth)
    _, df_slow, _ = detect_chords(y, sr, slow_hop, smooth)

    df = merge_resolutions(df_fast, df_slow)

    df = df[df["acorde"].notna()]
    df = df[df["acorde"] != ""].reset_index(drop=True)

    detected_key_raw = estimate_key_krumhansl(chroma)
    detected_key = normalize_key(detected_key_raw, df)

    if use_key_correction:
        df["acorde"] = df["acorde"].apply(lambda c: snap_to_scale(c, detected_key))
        df["acorde"] = df["acorde"].apply(lambda c: fix_chord_quality(c, detected_key))

    segs = [
        ChordSegment(row["inicio"], row["fin"], row["acorde"], row["confianza"])
        for _, row in df.iterrows()
    ]

    st.success(f"Tonalidad detectada: {detected_key} (raw: {detected_key_raw})")

    if transpose:
        base = detected_key.replace("m", "")
        shift = PITCH_CLASSES.index(target_key) - PITCH_CLASSES.index(base)
        df, segs = transpose_all(df, segs, shift)

    path = save_temp_audio(data, file.name)
    words = transcribe_words(path, language=None if lang == "auto" else lang)
    cleanup_temp_file(path)

    wdf = merge_words(words, segs)
    txt = build_text(wdf, gap, max_words)

    st.code(txt)
    st.dataframe(df)

    st.altair_chart(
        alt.Chart(df)
        .mark_bar()
        .encode(
            x="inicio",
            x2="fin",
            y="acorde",
            color="acorde",
            tooltip=["inicio", "fin", "duracion", "acorde", "confianza"],
        ),
        use_container_width=True,
    )