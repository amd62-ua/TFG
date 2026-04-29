import streamlit as st
import pandas as pd
from core.detector import DetectChords
from core.audio import convert_to_wav

st.title("🎵 Chord Detection App")

uploaded_file = st.file_uploader("Sube un audio", type=["mp3", "wav"])

if uploaded_file:
    with open(uploaded_file.name, "wb") as f:
        f.write(uploaded_file.read())

    st.audio(uploaded_file.name)

    if st.button("Procesar"):
        with st.spinner("Procesando..."):

            wav_file = convert_to_wav(uploaded_file.name)

            detector = DetectChords()
            detector.build_models()

            # 🔥 SOLO UNA VEZ
            timeline = detector.predict(wav_file)

            st.success("Procesado!")

            # ======================
            # Mostrar acordes
            # ======================
            st.subheader("Acordes detectados")

            for t in timeline[:20]:
                st.write(f"{t['start']}s - {t['end']}s → {t['chord']}")

            # ======================
            # Mostrar tabla bonita
            # ======================
            df = pd.DataFrame(timeline)
            st.dataframe(df)