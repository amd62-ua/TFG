class ChordSegment:
    def __init__(self, start, end, chord):
        self.start = start
        self.end = end
        self.chord = chord

def find_chord(segs, t):
    for s in segs:
        if s.start <= t < s.end:
            return s.chord

    return segs[-1].chord if segs else "N"

def merge_words(words, segs):

    rows = []

    prev = None
    BLACKLIST = [
        "subtítulos realizados por la comunidad de amara.org",
        "amara.org",
    ]

    for w in words:

        chord = find_chord(
            segs,
            w["start"]
        )

        text = w["word"].strip()

        if any(
            bad in text.lower()
            for bad in BLACKLIST
        ):
            continue

        rows.append({
            "word": w["word"],
            "start": w["start"],
            "end": w["end"],
            "chord": chord,
            "show_chord": chord != prev
        })

        prev = chord

    return rows