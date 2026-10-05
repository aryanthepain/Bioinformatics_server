/* Small formatting helpers shared across screens. */

export function formatCount(value: number): string {
  return value.toLocaleString("en-US");
}

/**
 * Parse a backend timestamp into milliseconds since 1970.
 * The backend sends microseconds (6 decimals); Safari only accepts 3, so we trim them.
 */
export function parseTimestamp(iso: string | null): number | null {
  if (!iso) {
    return null;
  }
  const milliseconds = Date.parse(iso.replace(/(\.\d{3})\d+/, "$1"));
  return Number.isNaN(milliseconds) ? null : milliseconds;
}

/** 42 s · 6:05 */
export function formatDuration(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  if (totalSeconds < 60) {
    return `${totalSeconds} s`;
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/** 14:02 in the user's own locale. */
export function formatClock(milliseconds: number): string {
  return new Date(milliseconds).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
