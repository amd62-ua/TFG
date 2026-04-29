import os

DATA_PATH = "data"

def simplify_chord(chord):
    chord = chord.strip()

    if chord in ["N", "silence", ""]:
        return "N"

    # separar raíz
    root = chord.split(":")[0]

    # normalizar bemoles (# opcional si quieres luego)
    root = root.replace("Bb", "A#") \
               .replace("Db", "C#") \
               .replace("Eb", "D#") \
               .replace("Gb", "F#") \
               .replace("Ab", "G#")

    if "min" in chord:
        return root + "m"

    if "maj" in chord or ":" not in chord:
        return root

    # todo lo raro → mayor
    return root


def clean_lab_file(path):
    new_lines = []

    with open(path, "r") as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split()

        if len(parts) < 3:
            continue

        start, end, chord = parts[0], parts[1], parts[2]

        chord = simplify_chord(chord)

        new_lines.append(f"{start} {end} {chord}\n")

    # sobrescribe archivo
    with open(path, "w") as f:
        f.writelines(new_lines)


# =========================
# PROCESAR TODO
# =========================
for song in os.listdir(DATA_PATH):
    song_path = os.path.join(DATA_PATH, song)

    if not os.path.isdir(song_path):
        continue

    for file in os.listdir(song_path):
        if file.endswith(".lab"):
            lab_path = os.path.join(song_path, file)
            print("Limpiando:", lab_path)
            clean_lab_file(lab_path)

print("✅ TODOS LOS LAB LIMPIOS")