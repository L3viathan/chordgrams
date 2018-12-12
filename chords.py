import re
import io

import click


def clump(iterable, n):
    i = iter(iterable)
    while True:
        try:
            N = [next(i) for _ in range(n)]
            yield tuple(N)
        except StopIteration:
            return


class Song:
    """An entire song"""

    def __init__(self, segments):
        self.segments = segments

    @classmethod
    def from_text(cls, text):
        segments = []
        last_label = None
        for part in text.split("\n\n"):
            try:
                segments.append(
                    Segment.from_text(part, default_label=last_label)
                )
            except ValueError:
                print("Couldn't convert")
                print(part)
                raise
            last_label = segments[-1].label
        return Song(segments=segments)

    def __str__(self):
        """Convert a song to a textual (monospace-requiring) format"""
        return "\n".join(str(seg) for seg in self.segments)

    def to_tex(self):
        return (
            "\\begin{song}[verse/numbered]{title={}, music={}}\n%s\n\\end{song}"
            % ("\n".join(seg.to_tex() for seg in self.segments),)
        )

    def __repr__(self):
        return "<Song: [{}]>".format(
            ", ".join(repr(seg) for seg in self.segments)
        )

    def __add__(self, other):
        """Transpose the entire song upwards."""
        if isinstance(other, int):
            return Song(segments=[segment + other for segment in self.segments])
        return NotImplemented

    def __iadd__(self, other):
        """Transpose the entire song upwards (in-place)."""
        if isinstance(other, int):
            for segment in self.segments:
                segment += other
            return self
        return NotImplemented

    def __sub__(self, other):
        """Transpose the entire song downwards."""
        if isinstance(other, int):
            return Song(segments=[segment - other for segment in self.segments])
        return NotImplemented

    def __pos__(self):
        """Change the entire song to use #s instead of bs."""
        return Song(segments=[+segment for segment in self.segments])

    def __neg__(self):
        """Change the entire song to use bs instead of #s."""
        return Song(segments=[-segment for segment in self.segments])


class Segment:
    """A part of a song, e.g. a verse or a chorus"""

    def __init__(self, *, label, lines):
        self.label = label
        self.lines = lines

    @classmethod
    def from_text(cls, text, *, default_label=None):
        """Try to extract text and chords from a text document"""
        lines = []
        if text.startswith("["):
            first, _, text = text.partition("\n")
            label = first[1:-1]
        else:
            label = default_label
        for cline, tline in clump(text.split("\n"), 2):
            if not cline and not tline:
                continue
            chords = {}
            for match in re.finditer(r"\S+", cline):
                chords[match.span()[0]] = Chord.from_text(match.group())
            lines.append((tline, chords))
        return Segment(label=label, lines=lines)

    def __str__(self):
        """Convert a segment to a textual (monospace-requiring) format"""
        buffer = io.StringIO()
        if self.label:
            buffer.write(f"[{self.label}]\n")
        for line, chords in self.lines:
            lo = 0
            cline = io.StringIO()
            for i in chords:
                chord = str(chords[i])
                spaces = i - lo
                cline.write(" " * spaces)
                cline.write(chord)
                lo += spaces + len(chord)
            buffer.write(cline.getvalue())
            buffer.write("\n")
            buffer.write(line)
            buffer.write("\n")
        return buffer.getvalue()

    def to_tex(self):
        buffer = io.StringIO()
        if self.label and any(
            self.label.lower().startswith(x)
            for x in ["verse", "chorus", "bridge"]
        ):
            label = self.label.split()[0].lower()
        else:
            label = "verse"
        buffer.write(fr"\begin{{{label}}}")
        buffer.write("\n")
        for line, chords in self.lines:
            for i, char in enumerate(line):
                if i in chords:
                    chord = str(chords[i])
                    buffer.write(fr"^{{{chord}}}")
                buffer.write(char)
            remaining = [k for k in chords if k > i]
            if remaining:
                for k in sorted(remaining):
                    chord = chords[k]
                    buffer.write(f" ^{{{chord}}}")
                buffer.write(r" \empty")
            buffer.write(" \\\\\n")
        buffer.write(fr"\end{{{label}}}")
        buffer.write("\n")
        return buffer.getvalue()

    def __add__(self, other):
        """Transpose a song a given amount of semitones upwards."""
        if isinstance(other, int):
            return Segment(
                label=self.label,
                lines=[
                    (tline, {k: v + other for k, v in cline.items()})
                    for tline, cline in self.lines
                ],
            )
        return NotImplemented

    def __iadd__(self, other):
        """Transpose a song a given amount of semitones upwards (in-place)."""
        if isinstance(other, int):
            for _, cline in self.lines:
                for chord in cline.values():
                    chord += other
            return self
        return NotImplemented

    def __sub__(self, other):
        """Transpose a song a given amount of semitones downwards."""
        if isinstance(other, int):
            return self + -other
        return NotImplemented

    def __pos__(self):
        """Change the entire segment to use #s instead of bs."""
        return Segment(
            label=self.label,
            lines=[
                (tline, {k: +v for k, v in cline.items()})
                for tline, cline in self.lines
            ],
        )

    def __neg__(self):
        """Change the entire segment to use bs instead of #s."""
        return Segment(
            label=self.label,
            lines=[
                (tline, {k: -v for k, v in cline.items()})
                for tline, cline in self.lines
            ],
        )


class Chord:
    """A chord.

    Chords contain base note, scale, preference for # vs b, modifiers such as
    "sus4", and an optional bass note.
    """

    mods = [
        "-",
        "5",
        "6",
        "7",
        "9",
        "11",
        "13",
        "maj7",
        "aug",
        "sus4",
        "sus2",
        "dim",
        "add9",
    ]
    notes = ["C", "", "D", "", "E", "F", "", "G", "", "A", "", "B"]

    def __init__(self, *, val, scale, shiftpref, mods, bass):
        self.mods = mods
        self.shiftpref = shiftpref
        self.scale = scale
        self.val = val % 12
        self.bass = bass % 12 if bass else bass

    @classmethod
    def from_text(cls, text):
        """
        Construct a chord from a textual representation.

        The textual representation is not very flexible and demands a specific
        format, one that is common, but not universal. In particular, no H note
        exists (but Bb), minor chords are expressed with a "m" (not by
        lowercasing the letter), and modifiers are 3–4 letter alphanumeric
        strings, not symbols like + or °.

        Examples: C D7 E# Fb G#7 Dsus G#sus4 Fmaj7sus4 Fmaug
        """
        main, text = text[0], text[1:]
        val = Chord.notes.index(main)

        if text and text[0] in "#b":
            shiftpref, text = text[0], text[1:]
            val = (val + "b#".index(shiftpref) * 2 - 1) % 12
        else:
            shiftpref = None

        if text and text[0] == "m" and text[1:3] != "aj":
            scale, text = "minor", text[1:]
        else:
            scale = "major"

        mods = []
        bass = None

        while text:
            for mod in Chord.mods:
                if text.startswith(mod):
                    mods.append(mod)
                    text = text[len(mod) :]
                    break
            else:
                if text.startswith("/"):
                    bass = Chord.notes.index(text[1])
                    text = text[2:]
                    if text:
                        bass = (bass + "b#".index(text[0]) * 2 - 1) % 12
                        text = text[1:]
                if text:
                    raise ValueError(f"Remaining mods: {text}")
        return Chord(
            val=val, scale=scale, mods=mods, shiftpref=shiftpref, bass=bass
        )

    def __str__(self):
        """Return the string representation of the chord."""
        main = self.num2str(self.val)
        mods = "".join(self.mods)
        scale = "m" if self.scale == "minor" else ""
        bass = f"/{self.num2str(self.bass)}" if self.bass is not None else ""
        return f"{main}{scale}{mods}{bass}"

    def __repr__(self):
        return (
            f"Chord(val={self.val!r}, scale={self.scale!r}, "
            f"mods={self.mods!r}, shiftpref={self.shiftpref!r})"
        )

    def __add__(self, other):
        """Transpose a chord a given amount of semitones upwards."""
        if isinstance(other, int):
            return Chord(
                val=self.val + other,
                scale=self.scale,
                mods=self.mods[:],
                shiftpref=self.shiftpref,
                bass=self.bass + other if self.bass else self.bass,
            )
        return NotImplemented

    def __iadd__(self, other):
        """Transpose a chord a given amount of semitones upwards (in-place)."""
        if isinstance(other, int):
            self.val = (self.val + other) % 12
            if self.bass:
                self.bass = (self.bass + other) % 12
            return self
        return NotImplemented

    def __sub__(self, other):
        """Transpose a chord a given amount of semitones downwards."""
        if isinstance(other, int):
            return self + -other
        return NotImplemented

    def __pos__(self):
        """Change the entire segment to use #s instead of bs."""
        return Chord(
            val=self.val,
            scale=self.scale,
            mods=self.mods,
            shiftpref="#",
            bass=self.bass,
        )

    def __neg__(self):
        """Change the entire segment to use bs instead of #s."""
        return Chord(
            val=self.val,
            scale=self.scale,
            mods=self.mods,
            shiftpref="b",
            bass=self.bass,
        )

    def num2str(self, num):
        """Convert a number to a note string."""
        text = Chord.notes[num]
        if not text:
            if self.shiftpref == "#":
                text = Chord.notes[num - 1] + "#"
            else:
                text = Chord.notes[num + 1 % 12] + "b"
        return text


@click.command()
@click.argument("file", type=click.File())
@click.option("--transpose", "-t", type=int)
@click.option("--prefer", "-p", type=click.Choice(["#", "b", "sharp", "flat"]))
@click.option(
    "--format", "-f", type=click.Choice(["plain", "tex"]), default="plain"
)
def cli(file, transpose, prefer, format):
    song = Song.from_text(file.read())
    if transpose:
        song += transpose
    if prefer:
        prefer = {"sharp": "#", "flat": "b"}.get(prefer, prefer)
        if prefer == "#":
            song = +song
        elif prefer == "b":
            song = -song
        else:
            raise ValueError("Unknown preference value {!r}".format(prefer))
    if format == "plain":
        print(song)
    elif format == "tex":
        print(song.to_tex())


if __name__ == "__main__":
    cli()
