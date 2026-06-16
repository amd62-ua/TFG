import sys
from pathlib import Path
import random
import json
import csv
import io

import streamlit as st
import streamlit.components.v1 as components

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from utils.random_songs import get_random_songs
from core.song_processor import process_song


PASSWORD = "T2f02G6"
BASE_SONGS_DIR = ROOT_DIR / "Canciones"

import streamlit as st

st.title("Evaluación")

if st.button("⬅ Volver"):
    st.session_state.page = "principal"
    st.experimental_rerun()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:

    st.title("🔒 Acceso restringido")

    password = st.text_input(
        "Contraseña",
        type="password"
    )

    if st.button("Entrar"):

        if password == PASSWORD:

            st.session_state.authenticated = True
            st.experimental_rerun()

        else:

            st.error(
                "Contraseña incorrecta"
            )

    st.stop()

st.title("Evaluación de canciones aleatorias")


lang = st.selectbox(
    "Idioma",
    ["es"],
    index=0
)

st.divider()

st.subheader(
    "🎲 Generador canciones aleatorias"
)

num_songs = st.radio(
    "Número de canciones",
    [1, 9],
    horizontal=True
)

if "songs" not in st.session_state:
    st.session_state.songs = None

if "selected_song" not in st.session_state:
    st.session_state.selected_song = None

if "selected_song_name" not in st.session_state:
    st.session_state.selected_song_name = ""

if "processed" not in st.session_state:
    st.session_state.processed = False

if st.button("Generar canciones"):

    st.session_state.songs = get_random_songs(
        num_songs
    )

    st.session_state.selected_song = None
    st.session_state.selected_song_name = ""
    st.session_state.processed = False


if st.session_state.songs:

    st.subheader("Canciones")

    num_cols = (
        1
        if len(st.session_state.songs) == 1
        else 3
    )

    cols = st.columns(num_cols)

    for i, song_data in enumerate(
        st.session_state.songs
    ):

    
        with cols[i % num_cols]:

            genre = song_data["genre"]
            song = song_data["song"]

            song_dir = (
                BASE_SONGS_DIR
                / genre
                / song
            )

            preview_file = random.choice([
                song_dir / "A.mp3",
                song_dir / "B.mp3"
            ])

            full_song = (
                song_dir
                / f"{song}.mp3"
            )

            st.markdown(
                f"""
                <div style="
                    height:120px;
                    border:1px solid #ddd;
                    border-radius:12px;
                    display:flex;
                    justify-content:center;
                    align-items:center;
                    text-align:center;
                    padding:10px;
                    margin-bottom:10px;
                ">
                    <strong>{song}</strong>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button(
                "Elegir",
                key=f"select_{song}",
                use_container_width=True
            ):

                st.session_state.preview_song = str(
                    preview_file
                )

                st.session_state.selected_song = str(
                    full_song
                )

                st.session_state.selected_song_name = (
                    song
                )

                st.session_state.processed = False



if st.session_state.selected_song:

    st.divider()

    st.subheader(
        st.session_state.selected_song_name
    )

    import base64

    with open(
        st.session_state.preview_song,
        "rb"
    ) as f:

        audio_bytes = f.read()

    audio_base64 = base64.b64encode(
        audio_bytes
    ).decode()

    import base64

    with open(
        st.session_state.preview_song,
        "rb"
    ) as f:

        audio_bytes = f.read()

    audio_base64 = base64.b64encode(
        audio_bytes
    ).decode()
    
    components.html(
        f"""
        <audio
            controls
            controlsList="nodownload noplaybackrate"
            style="width:100%;">
            <source
                src="data:audio/mp3;base64,{audio_base64}"
                type="audio/mpeg">
        </audio>
        """,
        height=70
    )

    if st.button(
        "Procesar canción"
    ):

        with st.spinner(
            "Procesando..."
        ):

            txt, timeline, rows = process_song(
                vocals_path=st.session_state.selected_song,
                instrumental_path=st.session_state.selected_song,
                language=lang
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

    st.subheader(
        "🎤 Letra con acordes"
    )

    st.markdown(
        f"```\n{txt}\n```"
    )

    st.download_button(
        label="⬇️ Descargar letra + acordes",
        data=txt,
        file_name="letra_acordes.txt",
        mime="text/plain"
    )

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

    csv_buffer = io.StringIO()

    writer = csv.writer(
        csv_buffer
    )

    writer.writerow(
        ["start", "end", "chord"]
    )

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

    lyrics_timeline = [
        {
            "word": r["word"],
            "start": r["start"],
            "end": r["end"]
        }
        for r in rows
    ]

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

    lyrics_csv = io.StringIO()

    writer = csv.writer(
        lyrics_csv
    )

    writer.writerow(
        ["word", "start", "end"]
    )

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

