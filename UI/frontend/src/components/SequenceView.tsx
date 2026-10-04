/*
 * The sequence written out residue by residue (60 per line, in blocks of 10),
 * with a coloured mark under each residue taken from one chosen track.
 */
import { useMemo, useState } from "react";
import type { Tone, Track } from "../api/types";
import "../styles/tones.css";
import "./SequenceView.css";

const RESIDUES_PER_LINE = 60;
const BLOCK_SIZE = 10;

interface SequenceViewProps {
  sequence: string;
  tracks: Track[];
}

export default function SequenceView({ sequence, tracks }: SequenceViewProps) {
  const [selectedKey, setSelectedKey] = useState(tracks[0]?.key ?? "");
  const track = tracks.find((candidate) => candidate.key === selectedKey) ?? tracks[0];
  const length = sequence.length;

  const tones = useMemo(() => {
    const perResidue = new Array<Tone | null>(length).fill(null);
    if (track) {
      for (const segment of track.segments) {
        const last = Math.min(length, segment.end);
        for (let residue = Math.max(1, segment.start); residue <= last; residue += 1) {
          perResidue[residue - 1] = segment.tone;
        }
      }
    }
    return perResidue;
  }, [track, length]);

  if (!track) {
    return null;
  }

  const lineStarts: number[] = [];
  for (let start = 0; start < length; start += RESIDUES_PER_LINE) {
    lineStarts.push(start);
  }

  return (
    <div className="seqview">
      {tracks.length > 1 && (
        <div className="seqview__controls" role="group" aria-label="Colour residues by">
          <span className="seqview__controls-label">Colour by</span>
          {tracks.map((candidate) => (
            <button
              key={candidate.key}
              type="button"
              className={`seqview__choice${candidate.key === track.key ? " seqview__choice--active" : ""}`}
              aria-pressed={candidate.key === track.key}
              onClick={() => setSelectedKey(candidate.key)}
            >
              {candidate.label}
            </button>
          ))}
        </div>
      )}

      <div className="seqview__scroll">
        <div className="seqview__lines">
          {lineStarts.map((lineStart) => {
            const lineEnd = Math.min(lineStart + RESIDUES_PER_LINE, length);
            const blockStarts: number[] = [];
            for (let blockStart = lineStart; blockStart < lineEnd; blockStart += BLOCK_SIZE) {
              blockStarts.push(blockStart);
            }
            return (
              <div key={lineStart} className="seqview__line">
                <span className="seqview__position">{lineStart + 1}</span>
                <span className="seqview__residues">
                  {blockStarts.map((blockStart) => (
                    <span key={blockStart} className="seqview__block">
                      {Array.from(sequence.slice(blockStart, Math.min(blockStart + BLOCK_SIZE, lineEnd)), (letter, offset) => {
                        const index = blockStart + offset;
                        const tone = tones[index];
                        return (
                          <span key={index} className="seqview__residue" title={`${letter}${index + 1}`}>
                            <span className="seqview__letter">{letter}</span>
                            <span className={`seqview__mark${tone ? ` tone--${tone}` : ""}`} />
                          </span>
                        );
                      })}
                    </span>
                  ))}
                </span>
                <span className="seqview__position seqview__position--end">{lineEnd}</span>
              </div>
            );
          })}
        </div>
      </div>

      {track.legend.length > 0 && (
        <ul className="seqview__legend" aria-label={`${track.label} legend`}>
          {track.legend.map((item) => (
            <li key={`${item.tone}|${item.label}`} className="seqview__legend-item">
              <span className={`seqview__swatch tone--${item.tone}`} aria-hidden="true" />
              {item.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
