"""Cleaning and validation of user-submitted protein sequences.

Accepted input:
  * a raw amino-acid sequence, in any case, with spaces, line breaks or
    position numbers (as copied from GenBank or UniProt pages), or
  * a single FASTA record (header line starting with ">" plus sequence).

A trailing "*" (stop codon from a translation) and alignment gaps ("-", ".")
are removed. The 20 standard amino-acid letters are used as they are.

The six other IUPAC letters are repaired when there are only a few of them,
each with the standard amino acid it most likely stands for:
  X  unknown            -> L  leucine, the most common amino acid in Swiss-Prot (9.6%)
  B  Asp or Asn         -> D  the more common of the two
  Z  Glu or Gln         -> E  the more common of the two
  J  Leu or Ile         -> L  the more common of the two
  U  selenocysteine     -> C  cysteine, its sulfur analogue
  O  pyrrolysine        -> K  lysine, from which it is made
(B -> D, Z -> E and U -> C are also how AlphaFold reads these letters.)

At most MAX_REPLACED_PERCENT of the residues (at least one) may be replaced,
and no more than MAX_REPLACED_RUN in a row. Beyond that the guesses would
start to drive the results (a run of unknowns hides a whole motif, and filling
it with leucines creates an artificial segment), so the sequence is rejected
and the user is asked to check it.

frontend/src/lib/sequence.ts mirrors these rules for instant feedback.
"""

from dataclasses import dataclass
from itertools import pairwise

from .config import MAX_SEQUENCE_LENGTH, MIN_SEQUENCE_LENGTH

STANDARD_AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")
NUCLEOTIDE_LETTERS = frozenset("ACGTUN")
REPLACEMENTS = {"X": "L", "B": "D", "Z": "E", "J": "L", "U": "C", "O": "K"}
GAP_CHARACTERS = frozenset("-.")
MAX_REPLACED_PERCENT = 5
MAX_REPLACED_RUN = 3
MAX_NAME_LENGTH = 80


class SequenceError(ValueError):
    """Raised with a message that can be shown directly to the user."""


@dataclass(frozen=True)
class Replacement:
    position: int  # 1-based, in the analysed sequence
    original: str
    replacement: str


@dataclass(frozen=True)
class ParsedSequence:
    sequence: str
    header: str | None
    replacements: tuple[Replacement, ...] = ()
    removed_gaps: int = 0


def max_replacements(length: int) -> int:
    """How many residues may be replaced in a sequence of this length."""
    return max(1, length * MAX_REPLACED_PERCENT // 100)


def _letter_counts(letters: list[str]) -> str:
    """['X', 'B', 'X'] -> 'X: 2, B: 1' (most frequent first)."""
    counts: dict[str, int] = {}
    for letter in letters:
        counts[letter] = counts.get(letter, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{letter}: {count}" for letter, count in ordered)


def _longest_run(positions: list[int]) -> tuple[int, int]:
    """(start, end) of the longest run of consecutive positions (the first one on ties)."""
    best_start = best_end = start = positions[0]
    for previous, current in pairwise(positions):
        if current != previous + 1:
            start = current
        if current - start > best_end - best_start:
            best_start, best_end = start, current
    return best_start, best_end


def parse_sequence(text: str) -> ParsedSequence:
    """Clean and validate user input, raising SequenceError if unusable."""
    lines = [line.strip() for line in text.strip().splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise SequenceError("Please paste a protein sequence.")

    header_count = sum(1 for line in lines if line.startswith(">"))
    header: str | None = None
    body = lines

    if header_count > 1:
        raise SequenceError(
            f"Please paste one sequence at a time (found {header_count} FASTA records)."
        )
    if header_count == 1:
        if not lines[0].startswith(">"):
            raise SequenceError("The FASTA header (the line starting with '>') must come first.")
        header = lines[0][1:].strip()[:MAX_NAME_LENGTH] or None
        body = lines[1:]

    sequence = "".join(
        character
        for character in "".join(body)
        if not character.isspace() and not character.isdigit()
    ).upper()
    sequence = sequence.rstrip("*")

    if not sequence:
        if header_count == 1:
            raise SequenceError("The FASTA record has a header but no sequence.")
        raise SequenceError("Please paste a protein sequence.")

    unsupported = sorted(
        {c for c in sequence if not ("A" <= c <= "Z") and c not in GAP_CHARACTERS and c != "*"}
    )
    if unsupported:
        shown = ", ".join(f"'{character}'" for character in unsupported[:10])
        raise SequenceError(
            f"Unsupported characters: {shown}. Only amino-acid letters are accepted."
        )

    removed_gaps = sum(1 for character in sequence if character in GAP_CHARACTERS)
    sequence = "".join(character for character in sequence if character not in GAP_CHARACTERS)
    if not sequence:
        raise SequenceError("The sequence contains only gap characters ('-' or '.').")

    stop = sequence.find("*")
    if stop >= 0:
        raise SequenceError(
            f"The sequence contains a stop codon ('*') at position {stop + 1}. "
            "Please paste only the translated protein."
        )

    if len(sequence) >= 20 and set(sequence) <= NUCLEOTIDE_LETTERS:
        raise SequenceError(
            "This looks like a DNA or RNA sequence. "
            "Please paste the protein (amino-acid) sequence instead."
        )

    if len(sequence) < MIN_SEQUENCE_LENGTH:
        raise SequenceError(
            f"The sequence is too short ({len(sequence)} residues). "
            f"The minimum is {MIN_SEQUENCE_LENGTH}."
        )
    if len(sequence) > MAX_SEQUENCE_LENGTH:
        raise SequenceError(
            f"The sequence is too long ({len(sequence):,} residues). "
            f"The maximum is {MAX_SEQUENCE_LENGTH:,}."
        )

    positions = [index + 1 for index, character in enumerate(sequence) if character in REPLACEMENTS]
    if positions:
        letters = [sequence[position - 1] for position in positions]
        limit = max_replacements(len(sequence))
        if len(positions) > limit:
            raise SequenceError(
                f"{len(positions)} of {len(sequence)} residues are not standard amino acids "
                f"({_letter_counts(letters)}). Up to {limit} ({MAX_REPLACED_PERCENT}%) can be "
                "replaced automatically, so please check the sequence."
            )
        start, end = _longest_run(positions)
        if end - start + 1 > MAX_REPLACED_RUN:
            raise SequenceError(
                f"Residues {start}–{end} are {end - start + 1} non-standard letters in a row "
                f"({sequence[start - 1:end]}). At most {MAX_REPLACED_RUN} in a row can be "
                "replaced automatically, so please check the sequence."
            )

    replacements = tuple(
        Replacement(position, sequence[position - 1], REPLACEMENTS[sequence[position - 1]])
        for position in positions
    )
    cleaned = "".join(REPLACEMENTS.get(character, character) for character in sequence)
    return ParsedSequence(
        sequence=cleaned, header=header, replacements=replacements, removed_gaps=removed_gaps
    )
