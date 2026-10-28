// Public Pages preview: browser-only data. Never connects to a controller or Codex.
const STORAGE_KEY = "hiyo-ui-preview-v1";
export function initialPreview() {
  const created = Date.now() / 1000;
  return {
    projects: [
      {
        id: "preview-project",
        name: "Customer experience platform",
        brief:
          "A sample business goal. Explore the interface or create your own browser-only project.",
        workspace: "preview/customer-platform",
        created,
      },
    ],
    tasks: [
      [
        "Discover the product architecture",
        "Define API boundaries, data models, and the delivery plan.",
      ],
      [
        "Build the customer onboarding flow",
        "Implement an accessible onboarding experience with meaningful acceptance tests.",
      ],
      [
        "Verify and package the release",
        "Run the required tests and build checks, review the diff, and write operating documentation.",
      ],
    ].map(([title, spec], i) => ({
      id: `preview-task-${i}`,
      project_id: "preview-project",
      title,
      spec,
      checks: [["python", "-m", "pytest", "-q"]],
      dependencies: i ? [`preview-task-${i - 1}`] : [],
      priority: 0,
      status: "queued",
      stage: "queued",
      attempts: 0,
      created: created + i,
      error: null,
      checkpoint: null,
    })),
    events: [],
    runs: [],
    artifacts: [],
    running: false,
    stopped: false,
    projects_root: "Browser preview — no filesystem access",
  };
}
export function previewRequest(state, path, body) {
  if (path === "/state") return structuredClone(state);
  if (path === "/login" || path === "/logout") return { preview: true };
  if (path === "/controller/start")
    throw new Error(
      "This is a UI preview. Install the Python controller to run Codex workers.",
    );
  if (path === "/controller/stop") {
    state.stopped = true;
    return { status: "preview stopped" };
  }
  if (path === "/controller/clear-stop") {
    state.stopped = false;
    return { status: "preview idle" };
  }
  if (path === "/projects") {
    if (!body.name?.trim() || body.brief?.length < 10)
      throw new Error(
        "Enter a name and a business goal of at least 10 characters.",
      );
    const id = crypto.randomUUID();
    state.projects.push({ ...body, id, created: Date.now() / 1000 });
    return { id };
  }
  const match = path.match(/^\/projects\/([^/]+)\/tasks$/);
  if (match) {
    if (!state.projects.some((p) => p.id === match[1]))
      throw new Error("Project not found");
    if (
      !body.title?.trim() ||
      body.spec?.length < 10 ||
      !Array.isArray(body.checks) ||
      !body.checks.length ||
      body.checks.some(
        (c) =>
          !Array.isArray(c) ||
          !c.length ||
          c.some((a) => typeof a !== "string" || !a),
      )
    )
      throw new Error(
        "Enter a title, acceptance criteria, and nonempty command arrays.",
      );
    const id = crypto.randomUUID();
    state.tasks.push({
      ...body,
      id,
      project_id: match[1],
      status: "queued",
      stage: "queued",
      attempts: 0,
      created: Date.now() / 1000,
      dependencies: [],
      error: null,
      checkpoint: null,
    });
    state.events.unshift({
      seq: Date.now(),
      task_id: id,
      role: "Preview",
      kind: "browser-only task queued",
      data: {
        summary: "Saved in this browser only. No code or tests executed.",
      },
      created: Date.now() / 1000,
    });
    return { id };
  }
  throw new Error("This operation requires the installed controller.");
}
export async function previewApi(path, body) {
  let state;
  try {
    state =
      JSON.parse(
        localStorage.getItem(STORAGE_KEY) ||
          localStorage.getItem("grofloo-ui-preview-v1"),
      ) || initialPreview();
  } catch {
    state = initialPreview();
  }
  const result = previewRequest(state, path, body);
  if (body !== undefined) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      throw new Error(
        "Enable browser storage to save preview projects and tasks.",
      );
    }
  }
  return result;
}
