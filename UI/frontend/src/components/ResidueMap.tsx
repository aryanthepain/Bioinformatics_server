/*
 * The residue map: several tracks drawn on one shared residue axis.
 *
 * Hovering (or clicking, then using the arrow keys) moves a crosshair across
 * every track at once, and the readout underneath lists what each track says
 * about that single residue.
 */
import { useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import type { LegendItem, Track } from "../api/types";
import "../styles/tones.css";
import "./ResidueMap.css";

export interface MapRow {
  key: string;
  label: string;
  caption: string;
  track: Track;
}

interface ResidueMapProps {
  rows: MapRow[];
  sequence: string;
  /** Accessible name, e.g. "Residue map of all structural levels". */
  label: string;
}

const TICK_STEPS = [5, 10, 20, 25, 50, 100, 200, 250, 500];

function tickPositions(length: number): number[] {
  const step = TICK_STEPS.find((candidate) => length / candidate <= 10) ?? 1000;
  const ticks = [1];
  for (let value = step; value < length; value += step) {
    ticks.push(value);
  }
  const last = ticks[ticks.length - 1];
  if (length - last >= step * 0.75) {
    ticks.push(length);
  } else if (ticks.length > 1) {
    ticks[ticks.length - 1] = length;
  } else {
    ticks.push(length);
  }
  return ticks;
}

/** For every residue (1-based), the index of the segment covering it, or -1. */
function residueIndex(track: Track, length: number): Int32Array {
  const index = new Int32Array(length + 1).fill(-1);
  track.segments.forEach((segment, position) => {
    const first = Math.max(1, segment.start);
    const last = Math.min(length, segment.end);
    for (let residue = first; residue <= last; residue += 1) {
      index[residue] = position;
    }
  });
  return index;
}

function describe(track: Track, segmentIndex: number): string {
  if (segmentIndex < 0) {
    return "—";
  }
  const segment = track.segments[segmentIndex];
  return (
    segment.label ??
    track.legend.find((item) => item.tone === segment.tone)?.label ??
    segment.tone.replace(/-/g, " ")
  );
}

function uniqueLegend(rows: MapRow[]): LegendItem[] {
  const seen = new Set<string>();
  const items: LegendItem[] = [];
  for (const row of rows) {
    for (const item of row.track.legend) {
      const id = `${item.tone}|${item.label}`;
      if (!seen.has(id)) {
        seen.add(id);
        items.push(item);
      }
    }
  }
  return items;
}

function position(residue: number, length: number): string {
  return `${((residue - 0.5) / length) * 100}%`;
}

export default function ResidueMap({ rows, sequence, label }: ResidueMapProps) {
  const length = sequence.length;
  const [active, setActive] = useState<number | null>(null);
  const lanesRef = useRef<HTMLDivElement>(null);

  const ticks = useMemo(() => tickPositions(length), [length]);
  const lookups = useMemo(() => rows.map((row) => residueIndex(row.track, length)), [rows, length]);
  const legend = useMemo(() => uniqueLegend(rows), [rows]);

  const facts =
    active === null
      ? []
      : rows.map((row, index) => ({ key: row.key, label: row.label, value: describe(row.track, lookups[index][active]) }));
  const residueLetter = active === null ? "" : sequence[active - 1];
  const valueText =
    active === null
      ? "No residue selected"
      : [`Residue ${active}, ${residueLetter}`, ...facts.map((fact) => `${fact.label}: ${fact.value}`)].join(". ");

  const residueAt = (clientX: number): number | null => {
    const element = lanesRef.current;
    if (!element) {
      return null;
    }
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0) {
      return null;
    }
    const fraction = (clientX - rect.left) / rect.width;
    return Math.min(length, Math.max(1, Math.floor(fraction * length) + 1));
  };

  const handlePointer = (event: PointerEvent<HTMLDivElement>) => {
    setActive(residueAt(event.clientX));
  };

  const handlePointerLeave = () => {
    if (document.activeElement !== lanesRef.current) {
      setActive(null);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const current = active ?? 1;
    const stride = event.shiftKey ? 10 : 1;
    let next: number;
    switch (event.key) {
      case "ArrowRight":
      case "ArrowUp":
        next = current + stride;
        break;
      case "ArrowLeft":
      case "ArrowDown":
        next = current - stride;
        break;
      case "Home":
        next = 1;
        break;
      case "End":
        next = length;
        break;
      case "Escape":
        lanesRef.current?.blur();
        return;
      default:
        return;
    }
    event.preventDefault();
    setActive(Math.min(length, Math.max(1, next)));
  };

  return (
    <div className="rmap">
      <div className="rmap__scroll">
        <div className="rmap__grid">
          <span aria-hidden="true" />
          <div className="rmap__axis" aria-hidden="true">
            {ticks.map((tick, index) => (
              <span
                key={tick}
                className={`rmap__tick${index === 0 ? " rmap__tick--first" : ""}${
                  index === ticks.length - 1 ? " rmap__tick--last" : ""
                }`}
                style={{ left: position(tick, length) }}
              >
                {tick}
              </span>
            ))}
          </div>

          <div className="rmap__labels" aria-hidden="true">
            {rows.map((row) => (
              <div key={row.key} className="rmap__label">
                <span className="rmap__label-title">{row.label}</span>
                <span className="rmap__label-caption">{row.caption}</span>
              </div>
            ))}
          </div>

          <div
            ref={lanesRef}
            className="rmap__lanes"
            tabIndex={0}
            role="slider"
            aria-label={label}
            aria-valuemin={1}
            aria-valuemax={length}
            aria-valuenow={active ?? 1}
            aria-valuetext={valueText}
            onPointerMove={handlePointer}
            onPointerDown={handlePointer}
            onPointerLeave={handlePointerLeave}
            onFocus={() => setActive((current) => current ?? 1)}
            onBlur={() => setActive(null)}
            onKeyDown={handleKeyDown}
          >
            {rows.map((row) => (
              <div key={row.key} className="rmap__lane">
                <div className={`rmap__bar rmap__bar--${row.track.style}`}>
                  {row.track.segments.map((segment, index) => (
                    <span
                      key={index}
                      className={`rmap__seg rmap__seg--${row.track.style} tone--${segment.tone}`}
                      style={{
                        left: `${((segment.start - 1) / length) * 100}%`,
                        width: `${((segment.end - segment.start + 1) / length) * 100}%`,
                      }}
                    >
                      {row.track.style === "blocks" && segment.label ? (
                        <span className="rmap__seg-label">{segment.label}</span>
                      ) : null}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {active !== null && (
              <span className="rmap__crosshair" style={{ left: position(active, length) }} aria-hidden="true" />
            )}
          </div>
        </div>
      </div>

      <div className="rmap__footer">
        <div className="rmap__readout" aria-hidden="true">
          {active === null ? (
            <span className="rmap__hint">Hover over the map to inspect a residue, or click it and use the arrow keys.</span>
          ) : (
            <>
              <span className="rmap__residue">
                <span className="rmap__aa">{residueLetter}</span>
                <span className="rmap__number">{active}</span>
              </span>
              <span className="rmap__facts">
                {facts.map((fact) => (
                  <span key={fact.key} className="rmap__fact">
                    <span className="rmap__fact-label">{fact.label}</span>
                    <span className="rmap__fact-value">{fact.value}</span>
                  </span>
                ))}
              </span>
            </>
          )}
        </div>
        {legend.length > 0 && (
          <ul className="rmap__legend" aria-label="Legend">
            {legend.map((item) => (
              <li key={`${item.tone}|${item.label}`} className="rmap__legend-item">
                <span className={`rmap__swatch tone--${item.tone}`} aria-hidden="true" />
                {item.label}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
