import tensorflow as tf
import numpy as np
import madmom as mm
from keras.models import load_model
from tensorflow.keras.layers import Input, Dense
from tensorflow.keras.models import Model
from tf2crf import CRF
from sklearn import preprocessing


class DetectChords:
    def __init__(self):
        self.seq_len = 1024
        self.num_classes = 25
        self.feat_dim = 128
        self.context_s = 7
        self.num_frames = 2 * self.context_s + 1

        # ⚠️ IMPORTANTE: prefijo correcto del checkpoint
        self.crf_weights = "models/model_01/crf"

        # modelo CNN convertido a channels_last
        self.cnn_net = "models/cnn_extractor_fixed.h5"

    def get_chord_labels(self):
        roots = ['A','B','C','D','E','F','G']
        natural = zip(roots, [0, 2, 3, 5, 7, 8, 10])

        note_map = {}
        for chord, num in natural:
            note_map[chord] = num
            note_map[chord+'m'] = num + 12
            if chord not in ['E', 'B']:
                note_map[chord + '#'] = (num + 1) % 12
                note_map[chord + '#'+'m'] = note_map[chord + '#'] + 12

        note_map['N'] = 24

        # ordenar por índice
        chords = sorted(note_map.items(), key=lambda x: x[1])
        return [c[0] for c in chords]

    def build_models(self):
        # ======================
        # CRF
        # ======================
        reg = tf.keras.regularizers.L2(1e-3)

        input_layer = Input(shape=(self.seq_len, self.feat_dim), dtype='float32')
        mid = Dense(self.num_classes, activation='linear', kernel_regularizer=reg)(input_layer)

        crf = CRF(dtype='float32')
        crf.sequence_lengths = self.seq_len
        crf.output_dim = self.num_classes

        output = crf(mid)
        model = Model(input_layer, output)

        # ⚠️ Para inferencia no necesitamos loss real
        model.compile(optimizer='adam')

        model.load_weights(self.crf_weights)
        self.crf = model

        # ======================
        # CNN (feature extractor)
        # ======================
        self.cnn = load_model(self.cnn_net)

    def one_hot(self, class_ids):
        oh = np.zeros((len(class_ids), self.num_classes), dtype=np.int32)
        oh[np.arange(len(class_ids)), class_ids] = 1
        return oh
    
    def compress_timeline(self, timeline, min_duration=0.6):
        if not timeline:
            return []

        # PASO 1: Comprimir acordes contiguos idénticos (tu lógica original)
        compressed = []
        prev = timeline[0].copy() # Usamos copy() para no mutar el original inesperadamente

        for cur in timeline[1:]:
            if cur["chord"] == prev["chord"]:
                prev["end"] = cur["end"]
            else:
                compressed.append(prev)
                prev = cur.copy()
        compressed.append(prev)

        # PASO 2: Eliminar acordes de corta duración (ruido/jitter)
        filtered = []
        for chord in compressed:
            duration = chord["end"] - chord["start"]
            
            # Si es el primer acorde o si supera el tiempo mínimo, lo conservamos
            if not filtered or duration >= min_duration:
                filtered.append(chord)
            else:
                # Si dura muy poco, lo consideramos "ruido".
                # Extendemos el acorde anterior para que cubra este hueco de tiempo.
                filtered[-1]["end"] = chord["end"]

        # PASO 3: Al eliminar el ruido, es posible que hayan quedado dos acordes iguales juntos.
        # Hacemos una última pasada rápida para unirlos.
        final_timeline = []
        if not filtered:
            return []
            
        prev = filtered[0]
        for cur in filtered[1:]:
            if cur["chord"] == prev["chord"]:
                prev["end"] = cur["end"]
            else:
                final_timeline.append(prev)
                prev = cur
        final_timeline.append(prev)

        return final_timeline
        
        
    def predict(self, wav_path):
        spec = mm.audio.spectrogram.LogarithmicFilteredSpectrogram(
            wav_path,
            num_channels=1,
            sample_rate=44100,
            fps=10,
            frame_size=8192,
            num_bands=24,
            fmin=65,
            fmax=2100,
            unique_filters=True
        )

        spec = np.array(spec)

        # padding contexto
        pad_start = np.tile(spec[0, :], (self.context_s, 1))
        pad_end = np.tile(spec[-1, :], (self.context_s, 1))
        spec = np.vstack((pad_start, spec, pad_end))

        # ======================
        # 🔥 EXTRAER FEATURES DE TODOS LOS FRAMES
        # ======================
        frames = []

        for i in range(spec.shape[0] - 2 * self.context_s):

            spec_frame = spec[i:self.num_frames+i, :]
            spec_frame = preprocessing.scale(spec_frame)

            spec_frame = spec_frame.T
            spec_frame = spec_frame.reshape((1, spec_frame.shape[0], spec_frame.shape[1], 1))

            features = self.cnn.predict(spec_frame, verbose=0)[0]
            frames.append(features)

        frames = np.array(frames)

        # ======================
        # 🔥 PROCESAR EN BLOQUES PARA EL CRF
        # ======================
        final_preds = []

        for i in range(0, len(frames), self.seq_len):

            batch = frames[i:i+self.seq_len]
            valid_len = len(batch)

            # padding si falta
            if valid_len < self.seq_len:
                pad = np.tile(batch[-1], (self.seq_len - valid_len, 1))
                batch = np.vstack([batch, pad])

            batch = batch.reshape((1, self.seq_len, self.feat_dim))

            pred = self.crf.predict(batch, verbose=0)[0]

            final_preds.extend(pred[:valid_len].flatten())

        final_preds = np.array(final_preds)

        # ======================
        # 🎵 CONVERTIR A TIMELINE
        # ======================
        chord_labels = self.get_chord_labels()
        fps = 10

        timeline = []

        for i, chord_id in enumerate(final_preds):
            start = i / fps
            end = (i + 1) / fps

            chord_name = chord_labels[int(chord_id)]

            timeline.append({
                "chord": chord_name,
                "start": round(start, 2),
                "end": round(end, 2)
            })

        # ======================
        # 🔥 COMPRIMIR ACORDES
        # ======================
        timeline = self.compress_timeline(timeline)

        return timeline