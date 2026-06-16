import sys
from pathlib import Path
import tempfile
import random
import json
import csv
import io
import base64
import shutil
import streamlit as st
import streamlit.components.v1 as components

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from core.song_processor import process_song
from utils.random_songs import get_random_songs
import gdown
with open(
    ROOT_DIR / "utils" / "canciones.json",
    encoding="utf-8"
) as f:

    SONGS = json.load(f)
PASSWORD = "T2f02G6"


import gdown
from pathlib import Path

TMP_DIR = Path("tmp_songs")
TMP_DIR.mkdir(exist_ok=True)

import shutil

def download_song(preview_id, full_id):

    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)

    TMP_DIR.mkdir(exist_ok=True)

    preview_path = TMP_DIR / "preview.mp3"
    full_path = TMP_DIR / "full.mp3"

    progress_text = st.empty()
    progress_bar = st.progress(0)

    progress_text.info("Cragando fragmento de audio...")

    gdown.download(
        f"https://drive.google.com/uc?id={preview_id}",
        str(preview_path),
        quiet=True
    )

    progress_bar.progress(50)

    progress_text.info("Cargando canción...")

    gdown.download(
        f"https://drive.google.com/uc?id={full_id}",
        str(full_path),
        quiet=True
    )

    progress_bar.progress(100)

    progress_text.success("Canción cargada correctamente")

    return str(preview_path), str(full_path)

def download_drive_file(file_id, output_path):

    url = f"https://drive.google.com/uc?id={file_id}"

    gdown.download(
        url,
        str(output_path),
        quiet=False
    )

    return output_path

# --------------------------------------------------
# CONFIGURACIÓN INICIAL
# --------------------------------------------------

st.set_page_config(
    page_title="Acordes + letra",
    layout="wide"
)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "main_processed" not in st.session_state:
    st.session_state.main_processed = False

if "eval_songs" not in st.session_state:
    st.session_state.eval_songs = None

if "eval_selected_song" not in st.session_state:
    st.session_state.eval_selected_song = None

if "eval_preview_song" not in st.session_state:
    st.session_state.eval_preview_song = None

if "eval_selected_song_name" not in st.session_state:
    st.session_state.eval_selected_song_name = ""

if "eval_processed" not in st.session_state:
    st.session_state.eval_processed = False


tab1, tab2 = st.tabs([
    "🎵 Procesador",
    "📊 Evaluación"
])


# ==================================================
# TAB 1 - PROCESADOR NORMAL
# ==================================================

with tab1:

    st.title("🎵 Acordes + letra sincronizada")

    main_lang = st.selectbox(
        "Idioma",
        ["es"],
        index=0,
        key="main_lang"
    )

    st.divider()

    mode = st.radio(
        "Modo",
        [
            "Audio completo",
            "Voz + instrumental separados"
        ],
        key="main_mode"
    )

    vocals_path = None
    instrumental_path = None

    if mode == "Audio completo":

        uploaded = st.file_uploader(
            "Sube audio",
            type=["mp3", "wav"],
            key="main_full_audio"
        )

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
            key="main_vocals"
        )

        instrumental = st.file_uploader(
            "Sube instrumental",
            type=["mp3", "wav"],
            key="main_instrumental"
        )

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

        if st.button(
            "Procesar",
            key="main_process"
        ):

            st.session_state.main_processed = False

            with st.spinner("Procesando..."):

                txt, timeline, rows = process_song(
                    vocals_path=vocals_path,
                    instrumental_path=instrumental_path,
                    language=main_lang
                )

                st.session_state.main_txt = txt
                st.session_state.main_timeline = timeline
                st.session_state.main_rows = rows
                st.session_state.main_processed = True

    if st.session_state.main_processed:

        txt = st.session_state.main_txt
        timeline = st.session_state.main_timeline
        rows = st.session_state.main_rows

        st.success("Procesado!")

        st.subheader("🎤 Letra con acordes")

        st.markdown(
            f"```\n{txt}\n```"
        )

        st.download_button(
            label="⬇️ Descargar letra + acordes",
            data=txt,
            file_name="letra_acordes.txt",
            mime="text/plain",
            key="main_download_txt"
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
            mime="application/json",
            key="main_download_chords_json"
        )

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
            mime="text/csv",
            key="main_download_chords_csv"
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
            mime="application/json",
            key="main_download_lyrics_json"
        )

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
            mime="text/csv",
            key="main_download_lyrics_csv"
        )


# ==================================================
# TAB 2 - EVALUACIÓN
# ==================================================

with tab2:

    st.title("📊 Evaluación")

    if not st.session_state.authenticated:

        st.subheader("🔒 Acceso restringido")

        password = st.text_input(
            "Contraseña",
            type="password",
            key="eval_password"
        )

        if st.button(
            "Entrar",
            key="eval_login"
        ):

            if password == PASSWORD:

                st.session_state.authenticated = True
                st.experimental_rerun()

            else:

                st.error("Contraseña incorrecta")

        st.stop()

    st.title("Evaluación de canciones aleatorias")

    eval_lang = st.selectbox(
        "Idioma",
        ["es"],
        index=0,
        key="eval_lang"
    )

    st.divider()

    st.subheader("🎲 Generador canciones aleatorias")

    num_songs = st.radio(
        "Número de canciones",
        [1, 9],
        horizontal=True,
        key="eval_num_songs"
    )

    if st.button(
        "Generar canciones",
        key="eval_generate_songs"
    ):

        st.session_state.eval_songs = get_random_songs(
            num_songs
        )

        st.session_state.eval_selected_song = None
        st.session_state.eval_preview_song = None
        st.session_state.eval_selected_song_name = ""
        st.session_state.eval_processed = False

    if st.session_state.eval_songs:

        st.subheader("Canciones")

        num_cols = (
            1
            if len(st.session_state.eval_songs) == 1
            else 3
        )

        cols = st.columns(num_cols)

        for i, song_data in enumerate(
            st.session_state.eval_songs
        ):

            with cols[i % num_cols]:

                genre = song_data["genre"]
                song = song_data["song"]

                 

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
                        <strong>{genre} - {song}</strong>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button(
                    "Elegir",
                    key=f"eval_select_{genre}_{song}_{i}",
                    use_container_width=True
                ):

                    song_info = SONGS[genre][song]

                    preview_id = random.choice([
                        song_info["preview_a"],
                        song_info["preview_b"]
                    ])

                    full_id = song_info["full"]

                    preview_path, full_path = download_song(
                        preview_id,
                        full_id
                    )

                    st.session_state.eval_preview_song = preview_path
                    st.session_state.eval_selected_song = full_path
                    st.session_state.eval_selected_song_name = f"{genre} - {song}"
                    st.session_state.eval_processed = False

    if st.session_state.eval_selected_song:

        st.divider()

        st.subheader(
            st.session_state.eval_selected_song_name
        )

        with open(
            st.session_state.eval_preview_song,
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
            "Procesar canción",
            key="eval_process_song"
        ):

            with st.spinner("Procesando..."):

                txt, timeline, rows = process_song(
                    vocals_path=st.session_state.eval_selected_song,
                    instrumental_path=st.session_state.eval_selected_song,
                    language=eval_lang
                )

                st.session_state.eval_txt = txt
                st.session_state.eval_timeline = timeline
                st.session_state.eval_rows = rows
                st.session_state.eval_processed = True

    if st.session_state.eval_processed:

        txt = st.session_state.eval_txt
        timeline = st.session_state.eval_timeline
        rows = st.session_state.eval_rows

        st.success("Procesado!")

        st.subheader("🎤 Letra con acordes")

        st.markdown(
            f"```\n{txt}\n```"
        )

        st.download_button(
            label="⬇️ Descargar letra + acordes",
            data=txt,
            file_name="letra_acordes.txt",
            mime="text/plain",
            key="eval_download_txt"
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
            mime="application/json",
            key="eval_download_chords_json"
        )

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
            mime="text/csv",
            key="eval_download_chords_csv"
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
            mime="application/json",
            key="eval_download_lyrics_json"
        )

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
            mime="text/csv",
            key="eval_download_lyrics_csv"
        )