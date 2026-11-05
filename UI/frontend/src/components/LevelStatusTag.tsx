import type { LevelReport, StepStatus } from "../api/types";

const STATUS_LABEL: Record<StepStatus, string> = {
  pending: "waiting",
  running: "running",
  completed: "done",
  failed: "failed",
  skipped: "skipped",
  cancelled: "stopped",
};

/** The small coloured tag next to a level's title: live, placeholder, running, failed… */
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
  return <span className="tag">{STATUS_LABEL[level.status]}</span>;
}
