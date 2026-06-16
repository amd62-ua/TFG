def detect_instrumental_gaps(rows, min_gap=4):
    gaps = []

    for i in range(len(rows) - 1):
        gap_start = rows[i]["end"]
        gap_end = rows[i + 1]["start"]

        if gap_end - gap_start > min_gap:
            gaps.append({
                "start": gap_start,
                "end": gap_end
            })

    return gaps


def build_instrumental_block(chords):
    line = "[Instrumental]\n"
    last = None

    for c in chords:
        if c.chord == "N":
            continue

        if c.chord != last:
            line += f"{c.chord}    "
            last = c.chord

    return line.strip()


def get_intro_chords(rows, segs):
    if not rows or not segs:
        return []

    first_word_time = rows[0]["start"]

    return [
        s for s in segs
        if s.start < first_word_time and s.chord != "N"
    ]


def get_gap_chords(segs, gap):
    return [
        s for s in segs
        if (
            s.start >= gap["start"]
            and s.end <= gap["end"]
            and s.chord != "N"
        )
    ]


def flush_lines(out, chord_line, lyric_line):
    if lyric_line:
        out.append(chord_line.rstrip())
        out.append(lyric_line.rstrip())
        out.append("")

    return "", ""


def should_break_by_pause(rows, index, start, word):
    if index == 0:
        return False

    prev_end = rows[index - 1]["end"]
    pause = start - prev_end

    return pause > 1.2 and word[:1].isupper()


def should_break_by_length(lyric_line, word, max_chars):
    return len(lyric_line) + len(word + " ") > max_chars


def get_active_chords(segs, start, end):
    return [
        s for s in segs
        if (
            s.end >= start
            and s.start <= end
            and s.chord != "N"
        )
    ]


def ensure_length(text, length):
    while len(text) < length:
        text += " "

    return text


def has_overlap(chord_line, pos, chord):
    for i in range(len(chord)):
        if (
            pos + i < len(chord_line)
            and chord_line[pos + i] != " "
        ):
            return True

    return False


def find_free_position(chord_line, pos, chord):
    while len(chord_line) < pos:
        chord_line += " "

    while (
        pos < len(chord_line)
        and any(
            c != " "
            for c in chord_line[pos:pos + len(chord)]
        )
    ):
        pos += 1

    return chord_line, pos


def insert_chord(chord_line, pos, chord):
    if pos >= len(chord_line):
        chord_line += " " * (pos - len(chord_line))
        chord_line += chord
    else:
        chord_line = (
            chord_line[:pos]
            + chord
            + chord_line[pos:]
        )

    return chord_line


def render_chords_for_word(
    chord_line,
    segs,
    word,
    start,
    end,
    cursor,
    rendered,
    last_rendered_chord
):
    duration = max(end - start, 0.001)
    active_chords = get_active_chords(segs, start, end)

    for s in active_chords:
        chord = s.chord

        if chord == last_rendered_chord:
            continue

        key = (round(s.start, 2), chord)

        if key in rendered:
            continue

        ratio = (s.start - start) / duration
        ratio = max(0, min(ratio, 1))

        offset = int(ratio * len(word))
        pos = cursor + offset

        chord_line = ensure_length(
            chord_line,
            pos + len(chord)
        )

        if has_overlap(chord_line, pos, chord):
            pos += 2

        chord_line, pos = find_free_position(
            chord_line,
            pos,
            chord
        )

        chord_line = insert_chord(
            chord_line,
            pos,
            chord
        )

        rendered.add(key)
        last_rendered_chord = chord

    return chord_line, rendered, last_rendered_chord


def render_instrumental_gaps(
    out,
    segs,
    gaps,
    rendered_gaps,
    start,
    chord_line,
    lyric_line
):
    for gap in gaps:
        key = (
            round(gap["start"], 2),
            round(gap["end"], 2)
        )

        if key in rendered_gaps:
            continue

        if start < gap["end"]:
            continue

        instrumental_chords = get_gap_chords(segs, gap)

        if not instrumental_chords:
            continue

        chord_line, lyric_line = flush_lines(
            out,
            chord_line,
            lyric_line
        )

        out.append(
            build_instrumental_block(
                instrumental_chords
            )
        )

        out.append("")
        rendered_gaps.add(key)

    return chord_line, lyric_line, rendered_gaps


def build_text(rows, segs, max_chars=42):
    out = []

    chord_line = ""
    lyric_line = ""

    rendered = set()
    rendered_gaps = set()
    last_rendered_chord = None

    instrumental_gaps = detect_instrumental_gaps(rows)

    intro_chords = get_intro_chords(rows, segs)

    if intro_chords:
        out.append(
            build_instrumental_block(intro_chords)
        )
        out.append("")

    for index, r in enumerate(rows):
        word = r["word"]
        start = r["start"]
        end = r["end"]

        chord_line, lyric_line, rendered_gaps = render_instrumental_gaps(
            out,
            segs,
            instrumental_gaps,
            rendered_gaps,
            start,
            chord_line,
            lyric_line
        )

        if lyric_line and should_break_by_pause(
            rows,
            index,
            start,
            word
        ):
            chord_line, lyric_line = flush_lines(
                out,
                chord_line,
                lyric_line
            )

        if should_break_by_length(
            lyric_line,
            word,
            max_chars
        ):
            chord_line, lyric_line = flush_lines(
                out,
                chord_line,
                lyric_line
            )

        cursor = len(lyric_line)

        lyric_line += word + " "

        chord_line = ensure_length(
            chord_line,
            len(lyric_line)
        )

        chord_line, rendered, last_rendered_chord = render_chords_for_word(
            chord_line,
            segs,
            word,
            start,
            end,
            cursor,
            rendered,
            last_rendered_chord
        )

    if lyric_line:
        out.append(chord_line.rstrip())
        out.append(lyric_line.rstrip())

    return "\n".join(out)