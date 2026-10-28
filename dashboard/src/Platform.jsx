import React, { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Plus,
  X,
  Layers,
  Workflow,
  Building2,
  Boxes,
  BrainCircuit,
  ShieldCheck,
  Play,
  Pause,
  Square,
  Check,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Plug,
  Search,
  FileText,
  Terminal,
  Clock3,
  SlidersHorizontal,
  Download,
  RefreshCw,
} from "lucide-react";
import "./platform.css";
const names = [
  "Command center",
  "Workflows",
  "Industry library",
  "Intelligence",
  "Connections",
  "Approvals",
  "Activity",
];
const icons = [
  Activity,
  Workflow,
  Building2,
  BrainCircuit,
  Plug,
  ShieldCheck,
  Clock3,
];
const empty = {
  workflows: [],
  runs: [],
  evidence: [],
  connectors: [],
  catalog: { industries: [], departments: [], templates: [] },
  stopped: false,
};
const labels = {
  transform: "Transform data",
  condition: "Condition",
  ai: "AI intelligence",
  approval: "Human approval",
  record: "Save outcome",
  connector: "Connected system",
};
const iconText = {
  HubSpot: "H",
  SAP: "SAP",
  Salesforce: "sf",
  Shopify: "S",
  Slack: "#",
  OpenAI: "◎",
  "Google Workspace": "G",
  "Microsoft 365": "M",
  Stripe: "S",
  "WhatsApp Business": "W",
  "Hiyo workspace": "h",
};
const newStep = (kind = "transform", i = 0) => ({
  id: "step_" + Date.now() + "_" + i,
  kind,
  name: labels[kind],
  template:
    kind === "approval"
      ? "Review before continuing."
      : kind === "connector"
        ? "{}"
        : "${request}",
  field: "",
  equals: "",
  connector_id: "",
  method: "GET",
  path: "/",
});
function State({ value }) {
  return (
    <span className={"state state-" + value}>
      {value?.replaceAll("_", " ")}
    </span>
  );
}
function Popover({ title, onClose, children }) {
  useEffect(() => {
    const key = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, []);
  return (
    <div
      className="platform-overlay"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section
        className="platform-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <button className="close" onClick={onClose} aria-label="Close dialog">
          <X size={20} />
        </button>
        <p className="eyebrow">HIYO / YOUR BUSINESS, CONNECTED</p>
        <h2>{title}</h2>
        {children}
      </section>
    </div>
  );
}
export default function Platform({
  api,
  preview,
  onEngineering,
  onLogout,
  refreshInterval = 3000,
  cloud = false,
}) {
  const [s, setS] = useState(empty),
    [tab, setTab] = useState("Command center"),
    [industry, setIndustry] = useState("all"),
    [query, setQuery] = useState(""),
    [modal, setModal] = useState(null),
    [selected, setSelected] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [steps, setSteps] = useState([newStep()]),
    [form, setForm] = useState({
      name: "",
      description: "",
      industry: "general",
      department: "Operations",
      trigger: "manual",
      interval_seconds: 3600,
    }),
    [draft, setDraft] = useState(null),
    [runInputs, setRunInputs] = useState("{}"),
    [goal, setGoal] = useState(""),
    [paid, setPaid] = useState(false),
    [decisionNote, setDecisionNote] = useState("");
  const refresh = async () => {
    try {
      setS(await api("/automation/state"));
    } catch (e) {
      setError(e.message);
    }
  };
  useEffect(() => {
    refresh();
    const timer = setInterval(() => {
      if (document.visibilityState !== "hidden") refresh();
    }, refreshInterval);
    return () => clearInterval(timer);
  }, []);
  const perform = async (path, body = {}, close = true) => {
    setBusy(true);
    try {
      const result = await api("/automation" + path, body);
      await refresh();
      setError("");
      if (close) setModal(null);
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setBusy(false);
    }
  };
  const flows = s.workflows.filter(
    (w) => industry === "all" || w.definition.industry === industry,
  );
  const ids = new Set(flows.map((w) => w.id)),
    runs = s.runs.filter((r) => ids.has(r.workflow_id));
  const pending = s.runs.filter((r) => r.status === "waiting_approval"),
    completed = runs.filter((r) => r.status === "completed"),
    blocked = runs.filter((r) => r.status === "blocked");
  const templates = s.catalog.templates.filter(
    (t) =>
      (industry === "all" ||
        t.industry === industry ||
        t.industry === "general") &&
      `${t.name} ${t.department} ${t.description}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const industryName = (id) =>
    s.catalog.industries.find((i) => i.id === id)?.name || id;
  const openBuilder = (definition = null) => {
    setForm(
      definition
        ? { ...definition }
        : {
            name: "",
            description: "",
            industry: industry === "all" ? "general" : industry,
            department: "Operations",
            trigger: "manual",
            interval_seconds: 3600,
          },
    );
    setSteps(definition?.steps || [newStep()]);
    setModal("builder");
  };
  const useTemplate = async (t) => {
    const result = await perform("/templates/" + t.id);
    if (result) {
      setTab("Workflows");
      setSelected(result.id);
    }
  };
  const openRun = (w) => {
    setSelected(w);
    const template = s.catalog.templates.find((t) => t.name === w.name);
    setRunInputs(
      JSON.stringify(
        template?.example || {
          name: "Your name",
          company: "Your company",
          request: "Describe the request",
        },
        null,
        2,
      ),
    );
    setModal("run");
  };
  const openEvidence = async (run) => {
    if (cloud) {
      try {
        const full = await api("/automation/runs/" + run.id);
        setSelected(full);
        setS((current) => ({
          ...current,
          evidence: [
            ...current.evidence.filter((e) => e.run_id !== run.id),
            ...full.evidence,
          ],
        }));
        setModal("evidence");
      } catch (e) {
        setError(e.message);
      }
    } else {
      setSelected(run);
      setModal("evidence");
    }
  };
  const recent = s.runs.slice(0, 5);
  return (
    <div className="platform">
      <aside className="platform-sidebar">
        <a
          className="platform-logo"
          href="#"
          onClick={() => setTab("Command center")}
        >
          <span>h·</span>
          <b>Hiyo</b>
          <small>AI AUTOMATION OS</small>
        </a>
        <div className="organization">
          <span>W</span>
          <div>
            <b>Your workspace</b>
            <small>
              {preview
                ? "Public interactive preview"
                : "Private business workspace"}
            </small>
          </div>
          <SlidersHorizontal size={14} />
        </div>
        <p className="side-label">WORKSPACE</p>
        <nav aria-label="Platform navigation">
          {names.map((name, i) => {
            const Icon = icons[i];
            return (
              <button
                key={name}
                onClick={() => {
                  setTab(name);
                  setQuery("");
                }}
                className={tab === name ? "selected" : ""}
              >
                <Icon size={17} />
                {name}
                {name === "Approvals" && pending.length > 0 && (
                  <em>{pending.length}</em>
                )}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="platform-hint">
            <BrainCircuit size={22} />
            <b>
              One intelligence layer.
              <br />
              Every department.
            </b>
            <p>
              Your systems keep working.
              <br />
              Hiyo brings them together.
            </p>
          </div>
          <button onClick={onEngineering}>
            <Terminal size={16} /> Engineering module <ArrowUpRight size={13} />
          </button>
          <button onClick={onLogout}>
            <span className="tiny-avatar">Y</span>Your account{" "}
            <ArrowRight size={14} />
          </button>
        </div>
      </aside>
      <div className="platform-body">
        <div className="platform-topbar">
          <div>
            <span className="dot" />
            {preview ? "Browser preview" : "Private platform"}
            <span className="top-separator">/</span>
            {tab}
          </div>
          <div>
            <ShieldCheck size={14} />
            <span>Human control, always</span>
            <button className="tiny-avatar" onClick={onLogout} title="Account">
              Y
            </button>
          </div>
        </div>
        <main className="platform-main">
          {preview && (
            <div className="platform-preview">
              <b>Interactive product preview</b>
              <span>
                Sample templates. Local workflows can run in your browser. AI
                and connected-system actions require the installed platform.
              </span>
            </div>
          )}
          <div className="platform-heading">
            <div>
              <p className="eyebrow">
                {tab === "Command center"
                  ? "THE INTELLIGENCE LAYER FOR YOUR BUSINESS"
                  : "YOUR BUSINESS / " + tab.toUpperCase()}
              </p>
              <h1>
                {
                  {
                    "Command center": "Every moving part. One clear view.",
                    Workflows: "Less busywork. More possibility.",
                    "Industry library": "Your industry. Your way of working.",
                    Intelligence: "Intelligence across every department.",
                    Connections: "Bring your business together.",
                    Approvals: "Human judgment, where it matters.",
                    Activity: "Every action leaves a trail.",
                  }[tab]
                }
              </h1>
              <p>
                {
                  {
                    "Command center":
                      "Connect your systems. Coordinate your teams. Turn information into action.",
                    Workflows:
                      "Design, run, and improve the work that keeps your business moving.",
                    "Industry library":
                      "Adapt proven workflow starters to your processes, systems, and policies.",
                    Intelligence:
                      "Understand the state of your operations using actual workflow evidence.",
                    Connections:
                      "Use APIs to connect your CRM, ERP, productivity tools, and custom systems.",
                    Approvals:
                      "Review AI usage and external actions before they happen.",
                    Activity:
                      "Run history, outcomes, approvals, and provider evidence in one place.",
                  }[tab]
                }
              </p>
            </div>
            <button className="platform-primary" onClick={() => openBuilder()}>
              <Plus size={16} />
              Create workflow
            </button>
          </div>
          {error && (
            <div className="platform-error" role="alert">
              {error}
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={15} />
              </button>
            </div>
          )}
          <div className="platform-filter">
            <label>
              <Building2 size={15} />
              <select
                aria-label="Industry filter"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
              >
                <option value="all">All industries</option>
                {s.catalog.industries.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name}
                  </option>
                ))}
              </select>
            </label>
            <span>{flows.length} workflows in view</span>
            <div className="filter-right">
              <span className="dot" />
              {s.stopped ? "Automation paused" : "Ready for your next move"}
              <button title="Refresh platform" onClick={refresh}>
                <RefreshCw size={14} />
              </button>
            </div>
          </div>
          {tab === "Command center" && (
            <>
              <div className="platform-stats">
                {[
                  {
                    label: "WORKFLOWS",
                    value: flows.length,
                    sub: `${flows.filter((w) => w.enabled).length} enabled`,
                    icon: Workflow,
                  },
                  {
                    label: "VERIFIED LOCAL OUTCOMES",
                    value: completed.length,
                    sub: preview
                      ? "Browser executions only"
                      : "Completed workflow runs",
                    icon: Check,
                  },
                  {
                    label: "AWAITING YOUR DECISION",
                    value: pending.length,
                    sub: "AI usage and sensitive actions",
                    icon: ShieldCheck,
                  },
                  {
                    label: "CONNECTED API ADAPTERS",
                    value: s.connectors.filter((c) => c.status === "verified")
                      .length,
                    sub: "Verified by a successful request",
                    icon: Plug,
                  },
                ].map((m) => (
                  <section className="platform-stat" key={m.label}>
                    <m.icon size={17} />
                    <small>{m.label}</small>
                    <strong>{m.value}</strong>
                    <span>{m.sub}</span>
                  </section>
                ))}
              </div>
              <div className="platform-command-grid">
                <section className="platform-card intelligence-map">
                  <div className="card-heading">
                    <div>
                      <p className="eyebrow">CONNECTED INTELLIGENCE</p>
                      <h2>A business that works together.</h2>
                    </div>
                    <Layers size={19} />
                  </div>
                  <div className="business-map">
                    <svg viewBox="0 0 600 280" aria-hidden="true">
                      <path
                        d="M90 65C200 65 140 140 300 140S410 65 510 65M90 215C200 215 140 140 300 140S410 215 510 215M90 140H510"
                        fill="none"
                        stroke="#d5d9ce"
                        strokeWidth="1.5"
                        strokeDasharray="4 5"
                      />
                    </svg>
                    <span className="business-core">
                      <BrainCircuit size={35} />
                      <b>hiyo</b>
                      <small>INTELLIGENCE ENGINE</small>
                    </span>
                    {[
                      "Sales & CRM",
                      "Finance",
                      "Operations",
                      "People & HR",
                      "Customer support",
                      "Marketing",
                    ].map((name, i) => (
                      <button
                        key={name}
                        className={"department-node dn-" + i}
                        onClick={() => setTab("Intelligence")}
                      >
                        <span>
                          {
                            [
                              <Activity />,
                              <Boxes />,
                              <Layers />,
                              <Building2 />,
                              <ShieldCheck />,
                              <Workflow />,
                            ][i]
                          }
                        </span>
                        {name}
                      </button>
                    ))}
                  </div>
                  <div className="map-footer">
                    <span>
                      <span className="dot" />
                      Adaptable to every industry
                    </span>
                    <button onClick={() => setTab("Connections")}>
                      Explore connections <ArrowUpRight size={13} />
                    </button>
                  </div>
                </section>
                <section className="platform-card next-move">
                  <p className="eyebrow">YOUR NEXT MOVE</p>
                  <span className="orbit-mark">
                    <BrainCircuit size={36} strokeWidth={1.1} />
                  </span>
                  <h2>
                    Tell Hiyo what
                    <br />
                    should happen next.
                  </h2>
                  <p>
                    Start with a business goal. Build the workflow, connect the
                    right systems, and keep control of every action.
                  </p>
                  <button
                    className="platform-primary"
                    onClick={() => {
                      setGoal("");
                      setPaid(false);
                      setModal("copilot");
                    }}
                  >
                    Design with AI <ArrowUpRight size={14} />
                  </button>
                  <button
                    className="platform-text"
                    onClick={() => setTab("Industry library")}
                  >
                    Or start from a template <ArrowRight size={14} />
                  </button>
                </section>
              </div>
              <div className="platform-section-heading">
                <div>
                  <p className="eyebrow">BUILT AROUND YOUR BUSINESS</p>
                  <h2>Find your first automation.</h2>
                </div>
                <button onClick={() => setTab("Industry library")}>
                  Explore the library <ArrowRight size={14} />
                </button>
              </div>
              <div className="template-grid">
                {templates.slice(0, 3).map((t) => (
                  <Template
                    key={t.id}
                    t={t}
                    industryName={industryName}
                    onUse={() => useTemplate(t)}
                  />
                ))}
              </div>
              <div className="platform-section-heading">
                <h2>Recent activity</h2>
                <button onClick={() => setTab("Activity")}>
                  View all activity <ArrowUpRight size={14} />
                </button>
              </div>
              <RunList
                runs={recent}
                onSelect={(r) => {
                  openEvidence(r);
                }}
              />
            </>
          )}
          {tab === "Workflows" && (
            <>
              <div className="workflow-grid">
                {flows.map((w) => (
                  <section className="platform-card workflow-card" key={w.id}>
                    <div className="card-heading">
                      <span className="module-icon">
                        <Workflow size={20} />
                      </span>
                      <State value={w.enabled ? "enabled" : "paused"} />
                    </div>
                    <p className="eyebrow">
                      {industryName(w.definition.industry)} /{" "}
                      {w.definition.department}
                    </p>
                    <h2>{w.name}</h2>
                    <p>
                      {w.definition.description || "Custom business automation"}
                    </p>
                    <div className="mini-flow">
                      {w.definition.steps.map((step, i) => (
                        <React.Fragment key={step.id}>
                          <span title={step.name}>
                            {step.kind === "ai" ? (
                              <BrainCircuit size={13} />
                            ) : step.kind === "approval" ? (
                              <ShieldCheck size={13} />
                            ) : step.kind === "connector" ? (
                              <Plug size={13} />
                            ) : (
                              <Layers size={13} />
                            )}
                          </span>
                          {i < w.definition.steps.length - 1 && (
                            <ChevronRight size={9} />
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                    <small>
                      {w.definition.steps.length} steps · {w.definition.trigger}
                      {w.definition.trigger === "schedule"
                        ? ` · every ${w.definition.interval_seconds}s`
                        : ""}
                    </small>
                    <div className="workflow-actions">
                      <button
                        className="platform-primary"
                        disabled={!w.enabled || s.stopped}
                        onClick={() => openRun(w)}
                      >
                        <Play size={13} />
                        Run workflow
                      </button>
                      <button
                        title={w.enabled ? "Pause workflow" : "Enable workflow"}
                        onClick={() =>
                          perform("/workflows/" + w.id + "/enabled", {
                            enabled: !w.enabled,
                          })
                        }
                      >
                        {w.enabled ? <Pause size={15} /> : <Play size={15} />}
                      </button>
                      <button
                        title="Duplicate in builder"
                        onClick={() =>
                          openBuilder({
                            ...w.definition,
                            name: w.name + " (copy)",
                          })
                        }
                      >
                        <Plus size={15} />
                      </button>
                    </div>
                  </section>
                ))}
              </div>
              {!flows.length && (
                <Empty
                  title="Make room for better work."
                  text="Create a workflow or adapt an industry template to get started."
                  onClick={() => setTab("Industry library")}
                  button="Explore industry templates"
                />
              )}
            </>
          )}
          {tab === "Industry library" && (
            <>
              <label className="platform-search">
                <Search size={16} />
                <input
                  placeholder="Search workflows, departments, or business outcomes"
                  aria-label="Search templates"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <div className="industry-chips">
                {s.catalog.industries.map((i) => (
                  <button
                    key={i.id}
                    className={industry === i.id ? "selected" : ""}
                    onClick={() =>
                      setIndustry(industry === i.id ? "all" : i.id)
                    }
                  >
                    {i.name}
                  </button>
                ))}
              </div>
              <div className="template-grid">
                {templates.map((t) => (
                  <Template
                    key={t.id}
                    t={t}
                    industryName={industryName}
                    onUse={() => useTemplate(t)}
                  />
                ))}
              </div>
            </>
          )}
          {tab === "Intelligence" && (
            <>
              <div className="intelligence-notice">
                <BrainCircuit size={23} />
                <div>
                  <b>Grounded in your workflow evidence.</b>
                  <p>
                    Department summaries below use recorded activity. Ask the AI
                    designer for a proposed workflow; provider usage always
                    needs your approval.
                  </p>
                </div>
                <button
                  className="platform-outline"
                  onClick={() => setModal("copilot")}
                >
                  Ask Hiyo <ArrowUpRight size={14} />
                </button>
              </div>
              <div className="department-grid">
                {s.catalog.departments.map((dept) => {
                  const ws = flows.filter(
                      (w) => w.definition.department === dept,
                    ),
                    wids = new Set(ws.map((w) => w.id)),
                    rs = runs.filter((r) => wids.has(r.workflow_id)),
                    needs = rs.filter((r) =>
                      ["blocked", "waiting_approval"].includes(r.status),
                    );
                  return (
                    <section
                      className="platform-card department-card"
                      key={dept}
                    >
                      <Layers size={22} />
                      <h2>{dept}</h2>
                      <p>
                        {ws.length
                          ? `${ws.length} workflows coordinate this department.`
                          : "Create a workflow to bring this department into view."}
                      </p>
                      <div>
                        <span>Completed outcomes</span>
                        <b>
                          {rs.filter((r) => r.status === "completed").length}
                        </b>
                      </div>
                      <div>
                        <span>Needs attention</span>
                        <b>{needs.length}</b>
                      </div>
                      <button
                        onClick={() => {
                          setForm({ ...form, department: dept });
                          setSteps([newStep()]);
                          setModal("builder");
                        }}
                      >
                        Build department workflow <ArrowRight size={13} />
                      </button>
                    </section>
                  );
                })}
              </div>
            </>
          )}
          {tab === "Connections" && (
            <>
              <div className="connection-intro">
                <div>
                  <h2>Your stack. Connected by design.</h2>
                  <p>
                    Native local actions, an OpenAI adapter, and a configurable
                    HTTPS API adapter for HubSpot, SAP, and other systems with
                    supported APIs. Credentials stay in operator-managed
                    environment bindings.
                  </p>
                </div>
                <button
                  className="platform-outline"
                  onClick={() => setModal("connector")}
                >
                  <Plus size={15} />
                  Universal connector
                </button>
              </div>
              <div className="connector-grid">
                {s.connectors.map((c) => (
                  <section className="platform-card connector-card" key={c.id}>
                    <div className="card-heading">
                      <span className="connector-logo">
                        {iconText[c.name] || c.name.slice(0, 2)}
                      </span>
                      <State value={c.status} />
                    </div>
                    <h2>{c.name}</h2>
                    <small>{c.category}</small>
                    <p>{c.description}</p>
                    {c.base_url && <code>{c.base_url}</code>}
                    <button
                      className="platform-text"
                      onClick={() => {
                        setSelected(c);
                        setModal("connection-detail");
                      }}
                    >
                      {c.id === "local"
                        ? "View capabilities"
                        : "Connection details"}{" "}
                      <ArrowUpRight size={13} />
                    </button>
                  </section>
                ))}
              </div>
            </>
          )}
          {tab === "Approvals" && (
            <>
              {pending.map((r) => {
                const step = r.workflow.steps[r.cursor];
                return (
                  <section className="platform-card approval-card" key={r.id}>
                    <div className="approval-icon">
                      <ShieldCheck size={24} />
                    </div>
                    <div>
                      <p className="eyebrow">
                        {step.kind === "ai"
                          ? "PAID AI USAGE"
                          : step.kind === "connector"
                            ? "EXTERNAL SYSTEM ACTION"
                            : "HUMAN REVIEW"}
                      </p>
                      <h2>{step.name}</h2>
                      <p>
                        {r.workflow.name} · {industryName(r.workflow.industry)}{" "}
                        · {r.workflow.department}
                      </p>
                      <p>
                        {step.kind === "ai"
                          ? "Approving permits one AI provider call for this step. Provider charges may apply."
                          : step.kind === "connector"
                            ? `${step.method} ${step.path} using connector ${step.connector_id}. Review the endpoint and run inputs before permitting this external request.`
                            : step.template}
                      </p>
                      <button
                        className="platform-text"
                        onClick={() => {
                          openEvidence(r);
                        }}
                      >
                        Review inputs and evidence <ArrowUpRight size={13} />
                      </button>
                    </div>
                    <div className="approval-actions">
                      <button
                        className="platform-primary"
                        disabled={busy || s.stopped}
                        onClick={async () => {
                          try {
                            setSelected(
                              cloud ? await api("/automation/runs/" + r.id) : r,
                            );
                            setDecisionNote("");
                            setModal("approve");
                          } catch (e) {
                            setError(e.message);
                          }
                        }}
                      >
                        <Check size={14} />
                        Review decision
                      </button>
                      <button
                        className="platform-text"
                        disabled={busy}
                        onClick={() =>
                          perform("/runs/" + r.id + "/decision", {
                            approve: false,
                            note: "Rejected by operator",
                          })
                        }
                      >
                        Reject
                      </button>
                    </div>
                  </section>
                );
              })}
              {!pending.length && (
                <Empty
                  title="Nothing waiting on you."
                  text="Human review, paid AI usage, and connected-system requests appear here before execution."
                />
              )}
            </>
          )}
          {tab === "Activity" && (
            <>
              <RunList
                runs={runs}
                onSelect={(r) => {
                  openEvidence(r);
                }}
              />
              {!runs.length && (
                <Empty
                  title="The next chapter is yours."
                  text="Run a workflow to see real step outputs, approvals, and outcomes here."
                />
              )}
            </>
          )}
          <footer className="platform-footer">
            <b>
              Hiyo<span>·</span>
            </b>
            <span>INTELLIGENCE THAT MOVES YOUR BUSINESS.</span>
            <button
              className="platform-text"
              onClick={() => setModal("safety")}
            >
              Controls & safety <ShieldCheck size={13} />
            </button>
          </footer>
        </main>
      </div>
      {modal === "builder" && (
        <Popover title="Build your workflow" onClose={() => setModal(null)}>
          <form
            className="workflow-builder"
            onSubmit={async (e) => {
              e.preventDefault();
              const result = await perform("/workflows", {
                ...form,
                interval_seconds: Number(form.interval_seconds),
                steps,
                enabled: true,
              });
              if (result) setTab("Workflows");
            }}
          >
            <div className="form-grid">
              <label>
                Workflow name
                <input
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="New customer onboarding"
                />
              </label>
              <label>
                Department
                <select
                  value={form.department}
                  onChange={(e) =>
                    setForm({ ...form, department: e.target.value })
                  }
                >
                  {s.catalog.departments.map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Business outcome
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                placeholder="What should happen, and what does a good outcome look like?"
              />
            </label>
            <div className="form-grid">
              <label>
                Industry
                <select
                  value={form.industry}
                  onChange={(e) =>
                    setForm({ ...form, industry: e.target.value })
                  }
                >
                  {s.catalog.industries.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                    </option>
                  ))}
                  <option value="custom">Custom industry</option>
                </select>
              </label>
              <label>
                Trigger
                <select
                  value={form.trigger}
                  onChange={(e) =>
                    setForm({ ...form, trigger: e.target.value })
                  }
                >
                  <option value="manual">Manual run</option>
                  <option value="webhook">Authenticated API trigger</option>
                  <option value="schedule">Recurring schedule</option>
                </select>
              </label>
            </div>
            {form.trigger === "schedule" && (
              <label>
                Interval in seconds (minimum 60)
                <input
                  required
                  type="number"
                  min="60"
                  max="31536000"
                  value={form.interval_seconds}
                  onChange={(e) =>
                    setForm({ ...form, interval_seconds: e.target.value })
                  }
                />
                <small>
                  Schedules require the installed platform. Input-free scheduled
                  workflows should not reference missing inputs. Pending or
                  blocked runs prevent duplicate scheduled runs.
                </small>
              </label>
            )}
            <div className="builder-step-heading">
              <b>Workflow steps</b>
              <small>
                Use $request, $name, $company, or a previous step ID in
                templates.
              </small>
            </div>
            {steps.map((step, i) => (
              <div className="builder-step" key={step.id}>
                <div className="step-heading">
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <input
                    aria-label={`Step ${i + 1} name`}
                    required
                    value={step.name}
                    onChange={(e) =>
                      setSteps(
                        steps.map((x, j) =>
                          j === i ? { ...x, name: e.target.value } : x,
                        ),
                      )
                    }
                  />
                  <button
                    type="button"
                    title="Move step up"
                    disabled={i === 0}
                    onClick={() => {
                      const n = [...steps];
                      [n[i - 1], n[i]] = [n[i], n[i - 1]];
                      setSteps(n);
                    }}
                  >
                    <ChevronUp size={14} />
                  </button>
                  <button
                    type="button"
                    title="Move step down"
                    disabled={i === steps.length - 1}
                    onClick={() => {
                      const n = [...steps];
                      [n[i + 1], n[i]] = [n[i], n[i + 1]];
                      setSteps(n);
                    }}
                  >
                    <ChevronDown size={14} />
                  </button>
                  <button
                    type="button"
                    title="Remove step"
                    disabled={steps.length === 1}
                    onClick={() => setSteps(steps.filter((_, j) => j !== i))}
                  >
                    <X size={14} />
                  </button>
                </div>
                <div className="form-grid">
                  <label>
                    Action
                    <select
                      value={step.kind}
                      onChange={(e) =>
                        setSteps(
                          steps.map((x, j) =>
                            j === i ? { ...x, kind: e.target.value } : x,
                          ),
                        )
                      }
                    >
                      {Object.entries(labels).map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Output reference
                    <input
                      required
                      pattern="[A-Za-z][A-Za-z0-9_]{0,49}"
                      value={step.id}
                      onChange={(e) =>
                        setSteps(
                          steps.map((x, j) =>
                            j === i ? { ...x, id: e.target.value } : x,
                          ),
                        )
                      }
                    />
                  </label>
                </div>
                {step.kind === "condition" ? (
                  <div className="form-grid">
                    <label>
                      Input or output field
                      <input
                        required
                        value={step.field}
                        onChange={(e) =>
                          setSteps(
                            steps.map((x, j) =>
                              j === i ? { ...x, field: e.target.value } : x,
                            ),
                          )
                        }
                      />
                    </label>
                    <label>
                      Equals
                      <input
                        value={step.equals}
                        onChange={(e) =>
                          setSteps(
                            steps.map((x, j) =>
                              j === i ? { ...x, equals: e.target.value } : x,
                            ),
                          )
                        }
                      />
                    </label>
                  </div>
                ) : (
                  <label>
                    {step.kind === "ai"
                      ? "AI instruction"
                      : step.kind === "approval"
                        ? "Review instructions"
                        : step.kind === "connector"
                          ? "Request body (JSON or SOAP XML)"
                          : "Template"}
                    <textarea
                      value={step.template}
                      onChange={(e) =>
                        setSteps(
                          steps.map((x, j) =>
                            j === i ? { ...x, template: e.target.value } : x,
                          ),
                        )
                      }
                    />
                  </label>
                )}
                {step.kind === "connector" && (
                  <>
                    <label>
                      Configured API connector
                      <select
                        required
                        value={step.connector_id}
                        onChange={(e) =>
                          setSteps(
                            steps.map((x, j) =>
                              j === i
                                ? { ...x, connector_id: e.target.value }
                                : x,
                            ),
                          )
                        }
                      >
                        <option value="">Select a configured connector</option>
                        {s.connectors
                          .filter((c) => c.base_url)
                          .map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <div className="form-grid">
                      <label>
                        Method
                        <select
                          value={step.method}
                          onChange={(e) =>
                            setSteps(
                              steps.map((x, j) =>
                                j === i ? { ...x, method: e.target.value } : x,
                              ),
                            )
                          }
                        >
                          {["GET", "POST", "PUT", "PATCH"].map((m) => (
                            <option key={m}>{m}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Endpoint path
                        <input
                          value={step.path}
                          onChange={(e) =>
                            setSteps(
                              steps.map((x, j) =>
                                j === i ? { ...x, path: e.target.value } : x,
                              ),
                            )
                          }
                          placeholder="/crm/v3/objects/contacts"
                        />
                      </label>
                    </div>
                  </>
                )}
              </div>
            ))}
            <button
              type="button"
              className="add-step"
              disabled={steps.length >= 20}
              onClick={() =>
                setSteps([...steps, newStep("transform", steps.length)])
              }
            >
              <Plus size={15} />
              Add step
            </button>
            <button className="platform-primary" disabled={busy}>
              Save workflow <ArrowRight size={15} />
            </button>
          </form>
        </Popover>
      )}
      {modal === "run" && (
        <Popover title={"Run " + selected.name} onClose={() => setModal(null)}>
          <p>
            Provide the inputs for this workflow. Local steps execute
            immediately; human review, AI calls, and external requests pause for
            a separate approval.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              try {
                const inputs = JSON.parse(runInputs);
                if (
                  !inputs ||
                  Array.isArray(inputs) ||
                  typeof inputs !== "object"
                )
                  throw Error("Inputs must be a JSON object");
                perform("/workflows/" + selected.id + "/trigger", {
                  inputs,
                }).then((r) => {
                  if (r) setTab("Activity");
                });
              } catch (e) {
                setError(e.message);
              }
            }}
          >
            <label>
              Input data (JSON)
              <textarea
                className="code-input"
                required
                value={runInputs}
                onChange={(e) => setRunInputs(e.target.value)}
              />
            </label>
            <button className="platform-primary" disabled={busy}>
              <Play size={14} />
              Start workflow
            </button>
          </form>
        </Popover>
      )}
      {modal === "evidence" && (
        <Popover title={selected.workflow.name} onClose={() => setModal(null)}>
          <div className="run-summary">
            <State value={selected.status} />
            <code>{selected.id}</code>
          </div>
          <h3>Inputs</h3>
          <pre>{JSON.stringify(selected.inputs, null, 2)}</pre>
          {selected.error && <p className="platform-error">{selected.error}</p>}
          <h3>Recorded evidence</h3>
          {s.evidence
            .filter((e) => e.run_id === selected.id)
            .reverse()
            .map((e) => (
              <details className="platform-evidence" key={e.seq}>
                <summary>
                  {e.step_id || "Workflow"}
                  <State value={e.kind} />
                </summary>
                <pre>{JSON.stringify(e.data, null, 2)}</pre>
              </details>
            ))}
          {selected.status === "blocked" && (
            <button
              className="platform-outline"
              onClick={() => perform("/runs/" + selected.id + "/resume")}
            >
              Resume after inspection <RefreshCw size={14} />
            </button>
          )}
        </Popover>
      )}
      {modal === "approve" && (
        <Popover
          title="Make an informed decision"
          onClose={() => setModal(null)}
        >
          <p>
            {selected.workflow.steps[selected.cursor].kind === "ai"
              ? "This approval authorizes one paid AI provider call. Review the inputs and instruction. Provider charges may apply."
              : selected.workflow.steps[selected.cursor].kind === "connector"
                ? "This approval authorizes one external API request using the configured connector. It may change a provider record. Review the method, path and body carefully."
                : "Review the preceding outputs before continuing."}
          </p>
          <pre>
            {JSON.stringify(
              {
                step: selected.workflow.steps[selected.cursor],
                inputs: selected.inputs,
                previous_outputs: selected.context,
              },
              null,
              2,
            )}
          </pre>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              perform("/runs/" + selected.id + "/decision", {
                approve: true,
                note: decisionNote,
              });
            }}
          >
            <label>
              Decision note
              <textarea
                value={decisionNote}
                onChange={(e) => setDecisionNote(e.target.value)}
                placeholder="Why is this action approved?"
              />
            </label>
            <label className="checkbox">
              <input type="checkbox" required />I have reviewed the action and
              authorize this step.
            </label>
            <button className="platform-primary" disabled={busy || s.stopped}>
              Approve this step <Check size={14} />
            </button>
          </form>
        </Popover>
      )}
      {modal === "connector" && (
        <Popover
          title="Hiyo Universal Connector"
          onClose={() => setModal(null)}
        >
          <p>
            Register an HTTPS API endpoint for HubSpot, SAP OData, your own
            service, or another API-enabled system. Store credential values
            securely in environment settings, never in this form.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              perform(
                "/connectors",
                Object.fromEntries(new FormData(e.target)),
              );
            }}
          >
            <label>
              System name
              <input name="name" required placeholder="HubSpot CRM" />
            </label>
            <label>
              HTTPS base URL
              <input
                name="base_url"
                type="url"
                required
                placeholder="https://api.hubapi.com"
              />
            </label>
            <label>
              Protocol
              <select name="protocol">
                <option value="rest">REST / JSON API</option>
                <option value="graphql">GraphQL</option>
                <option value="soap">SOAP / XML</option>
                <option value="webhook">Outbound webhook</option>
              </select>
            </label>
            <label>
              Authentication
              <select name="auth">
                <option value="bearer">Bearer token</option>
                <option value="api_key">API key header</option>
                <option value="basic">Basic (pre-encoded binding)</option>
                <option value="none">No authentication</option>
              </select>
            </label>
            <label>
              Credential variable name (not its value)
              <input
                name="credential_variable"
                pattern="HIYO_CONNECTOR_[A-Z0-9_]+"
                placeholder="HIYO_CONNECTOR_HUBSPOT"
              />
            </label>
            <label>
              API key header name
              <input name="header_name" defaultValue="X-API-Key" />
            </label>
            <p className="form-note">
              The operator must also permit the destination in
              HIYO_CONNECTOR_HOSTS and the cloud network policy. Creating a
              connector does not prove provider authorization. OAuth refresh and
              SAP schema-specific actions need separate provider setup.
            </p>
            <button className="platform-primary" disabled={busy}>
              Register connector <Plug size={15} />
            </button>
          </form>
        </Popover>
      )}
      {modal === "connection-detail" && (
        <Popover title={selected.name} onClose={() => setModal(null)}>
          <State value={selected.status} />
          <p>{selected.description}</p>
          {selected.base_url && (
            <pre>
              {JSON.stringify(
                {
                  base_url: selected.base_url,
                  credential_variable: selected.credential_variable,
                  host_allowed: selected.host_allowed,
                  credential_present: selected.credential_present,
                  last_success: selected.last_success,
                },
                null,
                2,
              )}
            </pre>
          )}
          {selected.id === "openai" ? (
            <p>
              Configure HIYO_AI_API_KEY securely for api.openai.com.
              HIYO_AI_MODEL selects the model (default gpt-4.1-mini). Every AI
              step pauses for paid-usage approval. No API key value is displayed
              here.
            </p>
          ) : (
            selected.id !== "local" && (
              <button
                className="platform-outline"
                onClick={() => setModal("connector")}
              >
                Configure an API connection <ArrowRight size={14} />
              </button>
            )
          )}
        </Popover>
      )}
      {modal === "copilot" && (
        <Popover
          title="Design with Hiyo intelligence"
          onClose={() => setModal(null)}
        >
          <p>
            Describe the business outcome. With an approved AI call, Hiyo can
            propose a workflow tailored to your industry and department. Review
            the proposed steps before saving.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const result = await perform(
                "/plan",
                {
                  goal,
                  industry: industry === "all" ? "general" : industry,
                  department: form.department,
                  approve_paid_usage: paid,
                },
                false,
              );
              if (result) {
                setDraft(result.workflow);
                setForm(result.workflow);
                setSteps(result.workflow.steps);
                setModal("builder");
              }
            }}
          >
            <label>
              Your automation goal
              <textarea
                minLength={10}
                required
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="When a new lead arrives in our CRM, prepare a qualification brief for the sales team to review."
              />
            </label>
            <label>
              Department
              <select
                value={form.department}
                onChange={(e) =>
                  setForm({ ...form, department: e.target.value })
                }
              >
                {s.catalog.departments.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                required
                checked={paid}
                onChange={(e) => setPaid(e.target.checked)}
              />
              I approve one paid AI request to propose this workflow.
            </label>
            <button className="platform-primary" disabled={busy}>
              Generate a proposed workflow <BrainCircuit size={15} />
            </button>
          </form>
          <button
            className="platform-text"
            onClick={() => {
              setModal(null);
              setTab("Industry library");
            }}
          >
            Use the template library instead <ArrowRight size={13} />
          </button>
        </Popover>
      )}
      {modal === "safety" && (
        <Popover
          title="Your automation controls"
          onClose={() => setModal(null)}
        >
          <p>
            Hiyo pauses for human review before paid AI calls and
            connected-system requests. An emergency stop prevents new runs and
            steps; already accepted external requests cannot be undone.
            Workflows have a 20-step limit, bounded payloads, and a 120-second
            execution window between calls.
          </p>
          <div className="safety-controls">
            <State value={s.stopped ? "stopped" : "ready"} />
            <button
              className="platform-outline"
              onClick={() => perform(s.stopped ? "/clear-stop" : "/stop")}
            >
              {s.stopped ? <Play size={14} /> : <Square size={14} />}{" "}
              {s.stopped
                ? "Clear automation stop"
                : "Emergency stop automations"}
            </button>
          </div>
          <p>
            Healthcare, finance, employment, legal, and other regulated
            decisions remain with qualified humans. This release is a private,
            single-operator platform foundation; multi-user enterprise
            permissions, tenant isolation, and compliance certification are not
            implemented.
          </p>
        </Popover>
      )}
    </div>
  );
}
function Template({ t, industryName, onUse }) {
  return (
    <section className="platform-card template-card">
      <div className="card-heading">
        <span className="module-icon">
          <Workflow size={19} />
        </span>
        <span className="template-category">{t.department}</span>
      </div>
      <h3>{t.name}</h3>
      <p>{t.description}</p>
      <div className="template-bottom">
        <span>
          {industryName(t.industry)}
          <small>
            {t.steps.length} steps ·{" "}
            {t.steps.some((s) => s.kind === "ai")
              ? "AI + human review"
              : "Local actions + review"}
          </small>
        </span>
        <button onClick={onUse} aria-label={"Use " + t.name}>
          <ArrowUpRight size={18} />
        </button>
      </div>
    </section>
  );
}
function Empty({ title, text, onClick, button }) {
  return (
    <div className="platform-empty">
      <Workflow size={34} />
      <h2>{title}</h2>
      <p>{text}</p>
      {button && (
        <button className="platform-outline" onClick={onClick}>
          {button}
          <ArrowRight size={14} />
        </button>
      )}
    </div>
  );
}
function RunList({ runs, onSelect }) {
  return (
    <div className="platform-runs">
      {runs.map((r) => (
        <button key={r.id} className="platform-run" onClick={() => onSelect(r)}>
          <span className="module-icon">
            <Activity size={16} />
          </span>
          <div>
            <b>{r.workflow.name}</b>
            <small>
              {r.workflow.department} ·{" "}
              {new Date(r.created * 1000).toLocaleString()}
            </small>
          </div>
          <State value={r.status} />
          <ChevronRight size={14} />
        </button>
      ))}
      {!runs.length && (
        <p className="runs-empty">
          No executions yet. Your actual workflow history will appear here.
        </p>
      )}
    </div>
  );
}
