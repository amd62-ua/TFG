import tensorflow as tf
import numpy as np
import madmom as mm
from keras.models import load_model
from tensorflow.keras.layers import Input, Dense
from tensorflow.keras.models import Model
from tf2crf import CRF
from sklearn import preprocessing
from pathlib import Path



class DetectChords:
    def __init__(self):
        self.seq_len = 1024
        self.num_classes = 25
        self.feat_dim = 128
        self.context_s = 7
        self.num_frames = 2 * self.context_s + 1

        
        BASE_DIR = Path(__file__).resolve().parent.parent

        self.crf_weights = BASE_DIR / "models" / "model_01" / "crf"

        self.cnn_net = BASE_DIR / "models" / "cnn_extractor_fixed.h5"

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

        
        chords = sorted(note_map.items(), key=lambda x: x[1])
        return [c[0] for c in chords]

    def build_models(self):
        
        reg = tf.keras.regularizers.L2(1e-3)

        input_layer = Input(shape=(self.seq_len, self.feat_dim), dtype='float32')
        mid = Dense(self.num_classes, activation='linear', kernel_regularizer=reg)(input_layer)

        crf = CRF(dtype='float32')
        crf.sequence_lengths = self.seq_len
        crf.output_dim = self.num_classes

        output = crf(mid)
        model = Model(input_layer, output)

        model.compile(optimizer='adam')

        model.load_weights(self.crf_weights)
        self.crf = model

        self.cnn = load_model(self.cnn_net)

    def one_hot(self, class_ids):
        oh = np.zeros((len(class_ids), self.num_classes), dtype=np.int32)
        oh[np.arange(len(class_ids)), class_ids] = 1
        return oh
    
    def compress_timeline(self, timeline, min_duration=1):
        if not timeline:
            return []

        compressed = []
        prev = timeline[0].copy() 

        for cur in timeline[1:]:
            if cur["chord"] == prev["chord"]:
                prev["end"] = cur["end"]
            else:
                compressed.append(prev)
                prev = cur.copy()
        compressed.append(prev)

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
        fps = 10

        spec = mm.audio.spectrogram.LogarithmicFilteredSpectrogram(
            wav_path,
            num_channels=1,
            sample_rate=44100,
            fps=fps,
            frame_size=8192,
            num_bands=24,
            fmin=65,
            fmax=2100,
            unique_filters=True
        )

        spec = np.array(spec)

        pad_start = np.tile(spec[0, :], (self.context_s, 1))
        pad_end = np.tile(spec[-1, :], (self.context_s, 1))
        spec = np.vstack((pad_start, spec, pad_end))

        batch_inputs = []

        for i in range(spec.shape[0] - 2 * self.context_s):
            spec_frame = spec[i:self.num_frames + i, :]
            spec_frame = preprocessing.scale(spec_frame)

            spec_frame = spec_frame.T
            spec_frame = spec_frame.reshape(
                spec_frame.shape[0],
                spec_frame.shape[1],
                1
            )

            batch_inputs.append(spec_frame)

        batch_inputs = np.array(batch_inputs)

        frames = self.cnn.predict(batch_inputs, verbose=0)

        final_preds = []

        for i in range(0, len(frames), self.seq_len):
            batch = frames[i:i + self.seq_len]
            valid_len = len(batch)

            if valid_len < self.seq_len:
                pad = np.tile(batch[-1], (self.seq_len - valid_len, 1))
                batch = np.vstack([batch, pad])

            batch = batch.reshape((1, self.seq_len, self.feat_dim))

            pred = self.crf.predict(batch, verbose=0)[0]

            final_preds.extend(pred[:valid_len].flatten())

        final_preds = np.array(final_preds)

        chord_labels = self.get_chord_labels()

        timeline = []

        for i, chord_id in enumerate(final_preds):
            start = i / fps
            end = (i + 1) / fps

            chord_name = chord_labels[int(chord_id)]

            if chord_name != "N":

                timeline.append({
                    "chord": chord_name,
                    "start": round(start, 2),
                    "end": round(end, 2)
                })

        timeline = self.compress_timeline(timeline)

        return timeline