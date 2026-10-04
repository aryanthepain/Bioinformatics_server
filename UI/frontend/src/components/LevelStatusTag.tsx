import type { LevelReport } from "../api/types";

/** The small coloured tag next to a level's title: live, placeholder, failed… */
export default function LevelStatusTag({ level }: { level: LevelReport }) {
  if (level.status === "completed" && level.result) {
    return level.result.source === "placeholder" ? (
      <span className="tag tag--placeholder">placeholder</span>
    ) : (
      <span className="tag tag--live">live</span>
    );
  }
  if (level.status === "failed") {
    return <span className="tag tag--danger">failed</span>;
  }
  return <span className="tag">{level.status}</span>;
}
