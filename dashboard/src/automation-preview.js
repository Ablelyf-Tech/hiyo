import catalog from "../../engineering_os/catalog.json" with { type: "json" };
const KEY = "hiyo-automation-preview-v1";
export function newAutomationState() {
  return {
    catalog,
    workflows: [],
    runs: [],
    evidence: [],
    stopped: false,
    connectors: [
      {
        id: "local",
        name: "Hiyo workspace",
        category: "Data & operations",
        status: "ready",
        description:
          "Real browser-only transformations, approvals and local records.",
      },
      {
        id: "openai",
        name: "OpenAI",
        category: "AI intelligence",
        status: "needs_configuration",
        description:
          "Provider execution requires the installed private controller.",
      },
      ...[
        "HubSpot",
        "SAP",
        "Salesforce",
        "Shopify",
        "Slack",
        "Microsoft 365",
        "Google Workspace",
        "Stripe",
        "WhatsApp Business",
      ].map((name) => ({
        id: name.toLowerCase().replaceAll(" ", "-"),
        name,
        category: "Business systems",
        status: "configurable",
        description:
          "Configure a provider API endpoint in the installed platform. No external connection is active in this preview.",
      })),
    ],
  };
}
function fill(template, context) {
  return template.replace(
    /\$\{([A-Za-z][A-Za-z0-9_]*)\}|\$([A-Za-z][A-Za-z0-9_]*)/g,
    (_, a, b) => {
      const key = a || b;
      if (!(key in context)) throw Error(`Missing input: ${key}`);
      return String(context[key]);
    },
  );
}
function evidence(s, r, step, kind, data) {
  s.evidence.unshift({
    seq: Date.now() + Math.random(),
    run_id: r.id,
    step_id: step,
    kind,
    data,
    created: Date.now() / 1000,
  });
}
function execute(s, r) {
  const approved = r.approved || [];
  r.status = "running";
  r.error = null;
  for (let i = r.cursor; i < r.workflow.steps.length; i++) {
    const step = r.workflow.steps[i];
    r.cursor = i;
    if (s.stopped) {
      r.status = "blocked";
      r.error = "Emergency stop is active";
      return;
    }
    if (
      ["approval", "ai", "connector"].includes(step.kind) &&
      !approved.includes(step.id)
    ) {
      r.status = "waiting_approval";
      evidence(s, r, step.id, "approval_required", {
        name: step.name,
        paid_service: step.kind === "ai",
        external_action: step.kind === "connector",
      });
      return;
    }
    if (["ai", "connector"].includes(step.kind)) {
      r.status = "blocked";
      r.error =
        "External AI and API connectors require the installed private platform. This preview never sends business data to providers.";
      evidence(s, r, step.id, "step_blocked", { error: r.error });
      return;
    }
    try {
      let output =
        step.kind === "approval"
          ? "Approved by the preview user"
          : fill(step.template || "", r.context);
      if (
        step.kind === "condition" &&
        String(r.context[step.field] ?? "") !== step.equals
      ) {
        r.status = "skipped";
        evidence(s, r, step.id, "condition_not_matched", { field: step.field });
        return;
      }
      r.context[step.id] = output;
      r.cursor = i + 1;
      evidence(s, r, step.id, "step_completed", {
        name: step.name,
        action_kind: step.kind,
        output,
        execution: "browser only",
      });
    } catch (e) {
      r.status = "blocked";
      r.error = e.message;
      return;
    }
  }
  r.status = "completed";
  r.updated = Date.now() / 1000;
  evidence(s, r, null, "completed", {
    steps: r.workflow.steps.length,
    execution: "browser only",
  });
}
export function automationPreviewRequest(s, path, body) {
  const route = path.replace(/^\/automation/, "");
  if (route === "/state") return structuredClone(s);
  if (route === "/workflows") {
    if (
      !body.name?.trim() ||
      !body.steps?.length ||
      body.steps.length > 20 ||
      new Set(body.steps.map((x) => x.id)).size !== body.steps.length
    )
      throw Error("A name and 1–20 uniquely named steps are required.");
    const id = crypto.randomUUID();
    s.workflows.unshift({
      id,
      name: body.name,
      definition: { ...body, trigger: body.trigger || "manual" },
      enabled: body.enabled !== false,
      created: Date.now() / 1000,
    });
    return { id };
  }
  let m = route.match(/^\/templates\/([^/]+)$/);
  if (m) {
    const t = catalog.templates.find((t) => t.id === m[1]);
    if (!t) throw Error("Template not found");
    return automationPreviewRequest(s, "/automation/workflows", {
      ...t,
      trigger: "manual",
      enabled: true,
    });
  }
  m = route.match(/^\/workflows\/([^/]+)\/(trigger|enabled)$/);
  if (m) {
    const w = s.workflows.find((w) => w.id === m[1]);
    if (!w) throw Error("Workflow not found");
    if (m[2] === "enabled") {
      w.enabled = body.enabled;
      return { enabled: w.enabled };
    }
    if (s.stopped || !w.enabled)
      throw Error("Workflow is paused or emergency stop is active");
    const r = {
      id: crypto.randomUUID(),
      workflow_id: w.id,
      workflow: structuredClone(w.definition),
      inputs: body.inputs || {},
      context: { ...body.inputs },
      approved: [],
      cursor: 0,
      status: "queued",
      created: Date.now() / 1000,
      updated: Date.now() / 1000,
    };
    s.runs.unshift(r);
    execute(s, r);
    return { id: r.id };
  }
  m = route.match(/^\/runs\/([^/]+)\/(decision|resume)$/);
  if (m) {
    const r = s.runs.find((r) => r.id === m[1]);
    if (!r) throw Error("Run not found");
    if (m[2] === "resume") {
      if (r.status !== "blocked") throw Error("Only blocked runs can resume");
      execute(s, r);
      return {};
    }
    if (r.status !== "waiting_approval")
      throw Error("Run is not waiting for approval");
    if (!body.approve) {
      r.status = "cancelled";
      evidence(s, r, null, "rejected", { note: body.note });
      return {};
    }
    const step = r.workflow.steps[r.cursor];
    r.approved.push(step.id);
    evidence(s, r, step.id, "approved", {
      note: body.note,
      actor: "preview user",
    });
    execute(s, r);
    return {};
  }
  if (route === "/stop" || route === "/clear-stop") {
    s.stopped = route === "/stop";
    return { stopped: s.stopped };
  }
  if (route === "/plan")
    throw Error(
      "AI workflow design requires the installed platform and a configured provider. Choose a template or use the visual builder in this preview.",
    );
  if (route === "/connectors")
    throw Error(
      "Provider connections are configured securely in the installed platform. This public preview never accepts credentials or makes external API requests.",
    );
  throw Error("Unknown automation operation");
}
export async function automationPreviewApi(path, body) {
  let s;
  try {
    s = JSON.parse(localStorage.getItem(KEY)) || newAutomationState();
  } catch {
    s = newAutomationState();
  }
  const result = automationPreviewRequest(s, path, body);
  if (body !== undefined) localStorage.setItem(KEY, JSON.stringify(s));
  return result;
}
