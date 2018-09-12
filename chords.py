import re
import io

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

    def to_tex(self):
        """Convert a song to TeX source"""
        ...

    def __str__(self):
        """Convert a song to a textual (monospace-requiring) format"""
        return "\n".join(str(seg) for seg in self.segments)


class Segment:
    """A part of a song, e.g. a verse or a chorus"""

    def __init__(self, *, label, lines):
        self.label = label
        self.lines = lines

    @classmethod
    def from_text(cls, text):
        """Try to extract text and chords from a text document"""
        lines = []
        for cline, tline in clump(text.split("\n"), 2):
            if not cline and not tline:
                continue
            chords = {}
            for match in re.finditer(r"\S+", cline):
                chords[match.span()[0]] = match.group()
            lines.append((tline, chords))
        return Segment(label=None, lines=lines)

    def to_tex(self):
        """Convert a segment to TeX source"""
        ...

    def __str__(self):
        """Convert a segment to a textual (monospace-requiring) format"""
        buffer = io.StringIO()
        for line, chords in self.lines:
            lo = 0
            cline = io.StringIO()
            for i in chords:
                spaces = i - lo
                cline.write(" "*spaces)
                cline.write(chords[i])
                lo += spaces + len(chords[i])
            buffer.write(cline.getvalue())
            buffer.write("\n")
            buffer.write(line)
            buffer.write("\n")
        return buffer.getvalue()

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
                (tline, {k: +v for k, v in cline.items()})
                for tline, cline in self.lines
            ],
        )

    def __add__(self, other):
        """Transpose a song a given amount of semitones upwards."""
        if isinstance(other, int):
            return Segment(
                label=self.label,
                lines=[
                    (tline, {k: v+other for k, v in cline.items()})
                    for tline, cline in self.lines
                ],
            )
        return NotImplemented

    def __sub__(self, other):
        """Transpose a song a given amount of semitones downwards."""
        if isinstance(other, int):
            return self + -other
        return NotImplemented

class Chord:
    """A chord.

    Chords contain base note, scale, preference for # vs b, modifiers such as
    "sus4", and an optional bass note.
    """
    mods = ["7", "9", "11", "13", "maj7", "aug", "sus4", "sus2", "dim"]
    notes = ['C', '', 'D', '', 'E', 'F', '', 'G', '', 'A', '', 'B']
    def __init__(self, *, val, scale, shiftpref, mods, bass):
        self.mods = mods
        self.shiftpref = shiftpref
        self.scale = scale
        self.val = val % 12
        self.bass = bass % 12 if bass else bass

    def __add__(self, other):
        """Transpose a song a given amount of semitones upwards."""
        if isinstance(other, int):
            return Chord(
                val=self.val+other,
                scale=self.scale,
                mods=self.mods[:],
                shiftpref=self.shiftpref,
                bass=self.bass+other,
            )
        return NotImplemented

    def __sub__(self, other):
        """Transpose a song a given amount of semitones downwards."""
        if isinstance(other, int):
            return self + -other
        return NotImplemented

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
            val = (val + "b#".index(shiftpref)*2-1) % 12
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
                    text = text[len(mod):]
                    break
            else:
                if text.startswith("/"):
                    bass = Chord.notes.index(text[1])
                    text = text[2:]
                    if text:
                        bass = (bass + "b#".index(text[0])*2-1) % 12
                        text = text[1:]
                if text:
                    raise ValueError(f"Remaining mods: {text}")
        return Chord(val=val, scale=scale, mods=mods, shiftpref=shiftpref, bass=bass)


    def __repr__(self):
        return (
            f"Chord(val={self.val!r}, scale={self.scale!r}, "
            f"mods={self.mods!r}, shiftpref={self.shiftpref!r})"
        )

    def num2str(self, num):
        """Convert a number to a note string."""
        text = Chord.notes[num]
        if not text:
            if self.shiftpref == "#":
                text = Chord.notes[num-1] + "#"
            else:
                text = Chord.notes[num+1 % 12] + "b"
        return text

    def __str__(self):
        """Return the string representation of the chord."""
        main = self.num2str(self.val)
        mods = "".join(self.mods)
        scale = "m" if self.scale == "minor" else ""
        bass = f"/{self.num2str(self.bass)}" if self.bass is not None else ""
        return f"{main}{scale}{mods}{bass}"

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
