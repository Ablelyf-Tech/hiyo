import test from "node:test";
import assert from "node:assert/strict";
import { initialPreview, previewRequest } from "../src/preview.js";
test("sample preview never invents executions or test results", () => {
  const s = initialPreview();
  assert.equal(s.running, false);
  assert.equal(s.events.length, 0);
  assert.equal(s.runs.length, 0);
  assert.ok(
    s.tasks.every(
      (t) => t.status === "queued" && t.attempts === 0 && !t.checkpoint,
    ),
  );
});
test("preview cannot execute Codex", () =>
  assert.throws(
    () =>
      previewRequest(initialPreview(), "/controller/start", {
        approve_codex_usage: true,
      }),
    /UI preview/,
  ));
test("browser-only projects and tasks can be created", () => {
  const s = initialPreview();
  const { id } = previewRequest(s, "/projects", {
    name: "Project",
    brief: "Build a useful product",
    workspace: "sample",
  });
  previewRequest(s, `/projects/${id}/tasks`, {
    title: "Build API",
    spec: "Build and test a simple API",
    checks: [["python", "-m", "pytest"]],
  });
  assert.equal(s.tasks.at(-1).project_id, id);
  assert.equal(s.events[0].role, "Preview");
  assert.equal(s.tasks.at(-1).status, "queued");
});
test("preview rejects invalid acceptance commands", () =>
  assert.throws(
    () =>
      previewRequest(initialPreview(), "/projects/preview-project/tasks", {
        title: "x",
        spec: "Valid acceptance criteria",
        checks: [],
      }),
    /nonempty/,
  ));
