/*
 * Instant, in-browser version of backend/app/sequence.py.
 * The backend re-checks everything; this only gives immediate feedback.
 * Keep the limits in sync with backend/app/config.py.
 */
import { formatCount } from "./format";

export const MIN_SEQUENCE_LENGTH = 25;
export const MAX_SEQUENCE_LENGTH = 1000;
const MAX_NAME_LENGTH = 80;

const STANDARD_AMINO_ACIDS = new Set("ACDEFGHIKLMNPQRSTVWY");
const NUCLEOTIDE_LETTERS = new Set("ACGTUN");

export type SequenceCheck =
  | { kind: "empty" }
  | { kind: "valid"; sequence: string; header: string | null }
  | { kind: "too-short"; length: number }
  | { kind: "invalid"; message: string };

export function checkSequence(text: string): SequenceCheck {
  const lines = text
    .trim()
    .split(/\r\n|[\n\r\u2028\u2029]/)
    .map((line) => line.trim())
    .filter((line) => line !== "");
  if (lines.length === 0) {
    return { kind: "empty" };
  }

  const headerCount = lines.filter((line) => line.startsWith(">")).length;
  if (headerCount > 1) {
    return {
      kind: "invalid",
      message: `Please paste one sequence at a time (found ${headerCount} FASTA records).`,
    };
  }

  let header: string | null = null;
  let body = lines;
  if (headerCount === 1) {
    if (!lines[0].startsWith(">")) {
      return {
        kind: "invalid",
        message: "The FASTA header (the line starting with '>') must come first.",
      };
    }
    header = lines[0].slice(1).trim().slice(0, MAX_NAME_LENGTH) || null;
    body = lines.slice(1);
  }

  const sequence = body
    .join("")
    .replace(/[\s\d]/g, "")
    .toUpperCase()
    .replace(/\*+$/, "");

  if (sequence === "") {
    return {
      kind: "invalid",
      message:
        headerCount === 1
          ? "The FASTA record has a header but no sequence."
          : "Please paste a protein sequence.",
    };
  }

  const characters = [...sequence];
  if (characters.length >= 20 && characters.every((character) => NUCLEOTIDE_LETTERS.has(character))) {
    return {
      kind: "invalid",
      message:
        "This looks like a DNA or RNA sequence. Please paste the protein (amino-acid) sequence instead.",
    };
  }

  const unsupported = [...new Set(characters.filter((character) => !STANDARD_AMINO_ACIDS.has(character)))].sort();
  if (unsupported.length > 0) {
    const shown = unsupported
      .slice(0, 10)
      .map((character) => `'${character}'`)
      .join(", ");
    return {
      kind: "invalid",
      message: `Unsupported characters: ${shown}. Only the 20 standard amino-acid letters are accepted.`,
    };
  }

  if (characters.length < MIN_SEQUENCE_LENGTH) {
    return { kind: "too-short", length: characters.length };
  }
  if (characters.length > MAX_SEQUENCE_LENGTH) {
    return {
      kind: "invalid",
      message: `The sequence is too long (${formatCount(characters.length)} residues). The maximum is ${formatCount(MAX_SEQUENCE_LENGTH)}.`,
    };
  }

  return { kind: "valid", sequence, header };
}
