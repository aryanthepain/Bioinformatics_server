/*
 * Instant, in-browser version of backend/app/sequence.py.
 * The backend re-checks everything; this only gives immediate feedback.
 * Keep the limits and replacement rules in sync with backend/app/sequence.py
 * and backend/app/config.py.
 */
import type { ResidueReplacement } from "../api/types";
import { formatCount } from "./format";

export const MIN_SEQUENCE_LENGTH = 25;
export const MAX_SEQUENCE_LENGTH = 1000;
const MAX_NAME_LENGTH = 80;

const NUCLEOTIDE_LETTERS = new Set("ACGTUN");
const GAP_CHARACTERS = new Set("-.");
export const MAX_REPLACED_PERCENT = 5;
export const MAX_REPLACED_RUN = 3;

/** Non-standard IUPAC letters, the standard amino acid used instead, and why. */
export const REPLACEMENT_RULES: Record<string, { replacement: string; reason: string }> = {
  X: { replacement: "L", reason: "unknown residue; leucine is the most common amino acid" },
  B: { replacement: "D", reason: "Asp or Asn; aspartate is the more common" },
  Z: { replacement: "E", reason: "Glu or Gln; glutamate is the more common" },
  J: { replacement: "L", reason: "Leu or Ile; leucine is the more common" },
  U: { replacement: "C", reason: "selenocysteine; cysteine is its sulfur analogue" },
  O: { replacement: "K", reason: "pyrrolysine; it is made from lysine" },
};

export type SequenceCheck =
  | { kind: "empty" }
  | {
      kind: "valid";
      sequence: string;
      header: string | null;
      replacements: ResidueReplacement[];
      removedGaps: number;
    }
  | { kind: "too-short"; length: number }
  | { kind: "invalid"; message: string };

/** How many residues may be replaced in a sequence of this length. */
export function maxReplacements(length: number): number {
  return Math.max(1, Math.floor((length * MAX_REPLACED_PERCENT) / 100));
}

/** ['X', 'B', 'X'] -> 'X: 2, B: 1' (most frequent first). */
function letterCounts(letters: string[]): string {
  const counts = new Map<string, number>();
  for (const letter of letters) {
    counts.set(letter, (counts.get(letter) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
    .map(([letter, count]) => `${letter}: ${count}`)
    .join(", ");
}

/** [start, end] of the longest run of consecutive positions (the first one on ties). */
function longestRun(positions: number[]): [number, number] {
  let bestStart = positions[0];
  let bestEnd = positions[0];
  let start = positions[0];
  for (let index = 1; index < positions.length; index++) {
    const current = positions[index];
    if (current !== positions[index - 1] + 1) {
      start = current;
    }
    if (current - start > bestEnd - bestStart) {
      bestStart = start;
      bestEnd = current;
    }
  }
  return [bestStart, bestEnd];
}

/** Replacements grouped by letter, for messages: "X → L at 50, 77 (unknown residue; …)". */
export function describeReplacements(replacements: ResidueReplacement[], maxPositions = 12): string[] {
  const groups = new Map<string, number[]>();
  for (const item of replacements) {
    const positions = groups.get(item.original) ?? [];
    positions.push(item.position);
    groups.set(item.original, positions);
  }
  return [...groups.entries()].map(([letter, positions]) => {
    const rule = REPLACEMENT_RULES[letter];
    const shown = positions.slice(0, maxPositions).map(formatCount).join(", ");
    const more = positions.length > maxPositions ? ` and ${positions.length - maxPositions} more` : "";
    const where = `${positions.length === 1 ? "position" : "positions"} ${shown}${more}`;
    return `${letter} → ${rule?.replacement ?? "?"} at ${where}${rule ? ` (${rule.reason})` : ""}`;
  });
}

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

  const raw = body
    .join("")
    .replace(/[\s\d]/g, "")
    .toUpperCase()
    .replace(/\*+$/, "");

  if (raw === "") {
    return {
      kind: "invalid",
      message:
        headerCount === 1
          ? "The FASTA record has a header but no sequence."
          : "Please paste a protein sequence.",
    };
  }

  const unsupported = [
    ...new Set(
      [...raw].filter(
        (character) => !(character >= "A" && character <= "Z") && !GAP_CHARACTERS.has(character) && character !== "*",
      ),
    ),
  ].sort();
  if (unsupported.length > 0) {
    const shown = unsupported
      .slice(0, 10)
      .map((character) => `'${character}'`)
      .join(", ");
    return {
      kind: "invalid",
      message: `Unsupported characters: ${shown}. Only amino-acid letters are accepted.`,
    };
  }

  const characters = [...raw].filter((character) => !GAP_CHARACTERS.has(character));
  const removedGaps = raw.length - characters.length;
  if (characters.length === 0) {
    return { kind: "invalid", message: "The sequence contains only gap characters ('-' or '.')." };
  }

  const stop = characters.indexOf("*");
  if (stop >= 0) {
    return {
      kind: "invalid",
      message: `The sequence contains a stop codon ('*') at position ${stop + 1}. Please paste only the translated protein.`,
    };
  }

  if (characters.length >= 20 && characters.every((character) => NUCLEOTIDE_LETTERS.has(character))) {
    return {
      kind: "invalid",
      message:
        "This looks like a DNA or RNA sequence. Please paste the protein (amino-acid) sequence instead.",
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

  const positions: number[] = [];
  characters.forEach((character, index) => {
    if (character in REPLACEMENT_RULES) {
      positions.push(index + 1);
    }
  });
  if (positions.length > 0) {
    const letters = positions.map((position) => characters[position - 1]);
    const limit = maxReplacements(characters.length);
    if (positions.length > limit) {
      return {
        kind: "invalid",
        message: `${positions.length} of ${characters.length} residues are not standard amino acids (${letterCounts(letters)}). Up to ${limit} (${MAX_REPLACED_PERCENT}%) can be replaced automatically, so please check the sequence.`,
      };
    }
    const [start, end] = longestRun(positions);
    if (end - start + 1 > MAX_REPLACED_RUN) {
      return {
        kind: "invalid",
        message: `Residues ${start}–${end} are ${end - start + 1} non-standard letters in a row (${characters.slice(start - 1, end).join("")}). At most ${MAX_REPLACED_RUN} in a row can be replaced automatically, so please check the sequence.`,
      };
    }
  }

  const replacements: ResidueReplacement[] = positions.map((position) => {
    const original = characters[position - 1];
    return { position, original, replacement: REPLACEMENT_RULES[original].replacement };
  });
  const sequence = characters.map((character) => REPLACEMENT_RULES[character]?.replacement ?? character).join("");
  return { kind: "valid", sequence, header, replacements, removedGaps };
}
