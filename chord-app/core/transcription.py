from faster_whisper import WhisperModel
import torch

_model = None

def load_whisper():
    global _model

    if _model is None:

        if torch.cuda.is_available():
            _model = WhisperModel(
                "medium",
                device="cuda",
                compute_type="float16"
            )
        else:
            _model = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8"
            )

    return _model

def transcribe_words(path, language="es"):
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