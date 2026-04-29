import os
import numpy as np
import librosa
import tensorflow as tf
from tensorflow.keras import layers
from tensorflow.keras.callbacks import EarlyStopping

# =========================
# CONFIG
# =========================
DATA_PATH = "data"
FPS = 10
CONTEXT = 7

# acordes (25 clases)
chord_list = [
    'C','C#','D','D#','E','F','F#','G','G#','A','A#','B',
    'Cm','C#m','Dm','D#m','Em','Fm','F#m','Gm','G#m','Am','A#m','Bm',
    'N'
]
chord_to_id = {c:i for i,c in enumerate(chord_list)}

# =========================
# FUNCIONES
# =========================
def extract_spec(path):
    y, sr = librosa.load(path, sr=44100)

    spec = librosa.feature.melspectrogram(
        y=y,
        sr=sr,
        n_fft=8192,
        hop_length=4410,
        n_mels=105,
        fmin=65,
        fmax=2100
    )

    spec = librosa.power_to_db(spec)
    return spec.T


def lab_to_frames(lab_file, total_frames):
    labels = np.zeros(total_frames, dtype=int)

    with open(lab_file) as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 3:
            continue

        start = float(parts[0])
        end = float(parts[1])
        chord = parts[2]

        if chord not in chord_to_id:
            chord = "N"

        start_f = int(start * FPS)
        end_f = int(end * FPS)

        labels[start_f:end_f] = chord_to_id[chord]

    return labels


def create_windows(X, y):
    X_out, y_out = [], []

    for i in range(CONTEXT, len(X)-CONTEXT):
        X_out.append(X[i-CONTEXT:i+CONTEXT+1])
        y_out.append(y[i])

    return np.array(X_out), np.array(y_out)


def load_dataset(song_list):
    all_X, all_y = [], []

    for song in song_list:
        song_path = os.path.join(DATA_PATH, song)

        wav, lab = None, None

        for file in os.listdir(song_path):
            if file.endswith(".wav"):
                wav = os.path.join(song_path, file)
            if file.endswith(".lab"):
                lab = os.path.join(song_path, file)

        if not wav or not lab:
            print("⚠️ Falta wav/lab en", song)
            continue

        print("Procesando:", song)

        spec = extract_spec(wav)
        labels = lab_to_frames(lab, len(spec))

        min_len = min(len(spec), len(labels))
        spec = spec[:min_len]
        labels = labels[:min_len]

        X, y = create_windows(spec, labels)

        X = X.transpose(0, 2, 1)
        X = X[..., np.newaxis]

        all_X.append(X)
        all_y.append(y)

    return np.concatenate(all_X), np.concatenate(all_y)


# =========================
# SPLIT POR CANCIONES
# =========================
songs = [s for s in os.listdir(DATA_PATH) if os.path.isdir(os.path.join(DATA_PATH, s))]
songs.sort()

split = int(len(songs) * 0.8)

train_songs = songs[:split]
val_songs = songs[split:]

print("Train:", train_songs)
print("Val:", val_songs)

# =========================
# CARGAR DATASETS
# =========================
X_train, y_train = load_dataset(train_songs)
X_val, y_val = load_dataset(val_songs)

print("Train shape:", X_train.shape)
print("Val shape:", X_val.shape)

# =========================
# MODELO (mejorado)
# =========================
model = tf.keras.Sequential([
    layers.Conv2D(16, 3, activation='relu', input_shape=(105,15,1)),
    layers.MaxPooling2D((2,1)),

    layers.Conv2D(32, 3, activation='relu'),
    layers.Dropout(0.3),

    layers.Flatten(),

    layers.Dense(64, activation='relu'),
    layers.Dropout(0.3),

    layers.Dense(len(chord_list), activation='softmax')
])

model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# =========================
# CALLBACKS
# =========================
early_stop = EarlyStopping(
    monitor='val_loss',
    patience=3,
    restore_best_weights=True
)

# =========================
# ENTRENAR
# =========================
model.fit(
    X_train,
    y_train,
    validation_data=(X_val, y_val),
    epochs=20,
    batch_size=32,
    callbacks=[early_stop]
)

# =========================
# GUARDAR
# =========================
model.save("models/new_model.h5")

print("✅ Modelo entrenado correctamente")