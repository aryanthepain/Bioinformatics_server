"""Cleaning and validation of user-submitted protein sequences.

Accepted input:
  * a raw amino-acid sequence, in any case, with spaces, line breaks or
    position numbers (as copied from GenBank or UniProt pages), or
  * a single FASTA record (header line starting with ">" plus sequence).

A trailing "*" (stop codon from a translation) is removed. Everything else
must be one of the 20 standard amino-acid letters.
"""

from dataclasses import dataclass

from .config import MAX_SEQUENCE_LENGTH, MIN_SEQUENCE_LENGTH

STANDARD_AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")
NUCLEOTIDE_LETTERS = frozenset("ACGTUN")
MAX_NAME_LENGTH = 80


class SequenceError(ValueError):
    """Raised with a message that can be shown directly to the user."""


@dataclass(frozen=True)
class ParsedSequence:
    sequence: str
    header: str | None


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

    if len(sequence) >= 20 and set(sequence) <= NUCLEOTIDE_LETTERS:
        raise SequenceError(
            "This looks like a DNA or RNA sequence. "
            "Please paste the protein (amino-acid) sequence instead."
        )

    invalid = sorted(set(sequence) - STANDARD_AMINO_ACIDS)
    if invalid:
        shown = ", ".join(f"'{character}'" for character in invalid[:10])
        raise SequenceError(
            f"Unsupported characters: {shown}. "
            "Only the 20 standard amino-acid letters are accepted."
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

    return ParsedSequence(sequence=sequence, header=header)
