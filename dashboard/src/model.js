export const roles = [
  "Planner",
  "Architect",
  "Builder",
  "Tester",
  "Debugger",
  "Reviewer",
  "Delivery Manager",
];
export function metrics(tasks) {
  const completed = tasks.filter((t) => t.status === "completed").length;
  return {
    completed,
    remaining: tasks.length - completed,
    progress: tasks.length ? Math.round((completed / tasks.length) * 100) : 0,
  };
}
export function duration(seconds) {
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}
