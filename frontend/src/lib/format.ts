export function formatTime(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function greeting(date = new Date()): string {
  const hour = date.getHours();
  if (hour < 5) return "Still up";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function stageLabel(stage: string | undefined): string {
  if (stage === "hybrid") return "Hybrid ranking is on. Listening history now carries collaborative weight.";
  if (stage === "content_with_early_feedback") {
    return "Early listening is nudging your profile. Collaborative filtering is not applied to these picks yet.";
  }
  return "Cold start. These picks use your onboarding answers until you have a short listening history.";
}

export function titleCase(value: string): string {
  return value.replace(/-/g, " ");
}
