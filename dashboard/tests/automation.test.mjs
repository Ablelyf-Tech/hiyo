import test from "node:test";
import assert from "node:assert/strict";
import {
  newAutomationState,
  automationPreviewRequest,
} from "../src/automation-preview.js";
test("industry library has no invented business outcomes", () => {
  const s = newAutomationState();
  assert.ok(s.catalog.industries.length >= 10);
  assert.ok(s.catalog.templates.length >= 14);
  assert.equal(s.runs.length, 0);
  assert.equal(s.evidence.length, 0);
});
test("local preview transformations and approvals produce actual browser evidence", () => {
  const s = newAutomationState();
  const flow = automationPreviewRequest(
    s,
    "/automation/templates/client-onboarding",
    {},
  );
  const run = automationPreviewRequest(
    s,
    `/automation/workflows/${flow.id}/trigger`,
    {
      inputs: { name: "Morgan", company: "Acme", request: "Onboard a client" },
    },
  );
  assert.equal(s.runs[0].status, "waiting_approval");
  assert.match(s.runs[0].context.intake, /Morgan/);
  automationPreviewRequest(s, `/automation/runs/${run.id}/decision`, {
    approve: true,
    note: "Reviewed",
  });
  assert.equal(s.runs[0].status, "completed");
  assert.ok(
    s.evidence.some(
      (e) => e.kind === "step_completed" && e.data.execution === "browser only",
    ),
  );
});
test("public preview never sends data to an AI provider or business system", () => {
  const s = newAutomationState();
  const f = automationPreviewRequest(
    s,
    "/automation/templates/support-triage",
    {},
  );
  const r = automationPreviewRequest(
    s,
    `/automation/workflows/${f.id}/trigger`,
    { inputs: { name: "Morgan", company: "Acme", request: "Support" } },
  );
  assert.equal(s.runs[0].status, "waiting_approval");
  automationPreviewRequest(s, `/automation/runs/${r.id}/decision`, {
    approve: true,
  });
  assert.equal(s.runs[0].status, "blocked");
  assert.match(s.runs[0].error, /never sends/);
});
test("emergency stop prevents new browser runs", () => {
  const s = newAutomationState();
  const f = automationPreviewRequest(
    s,
    "/automation/templates/client-onboarding",
    {},
  );
  automationPreviewRequest(s, "/automation/stop", {});
  assert.throws(
    () =>
      automationPreviewRequest(s, `/automation/workflows/${f.id}/trigger`, {
        inputs: {},
      }),
    /stop/,
  );
});
