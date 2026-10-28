import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowRight,
  Play,
  Pause,
  Square,
  Plus,
  X,
  Check,
  ChevronRight,
  GitBranch,
  ShieldCheck,
  Terminal,
  Activity,
  Box,
  Layers,
  Settings2,
  Download,
  Clock3,
  LockKeyhole,
  CircleHelp,
  Zap,
  FileText,
  RotateCcw,
  Search,
  LogOut,
} from "lucide-react";
import { roles, metrics, duration } from "./model";
import "./style.css";
import { previewApi } from "./preview";
import { automationPreviewApi } from "./automation-preview";
import Platform from "./Platform";
const CloudShell = React.lazy(() => import("./CloudShell"));
const IS_PREVIEW = import.meta.env.VITE_DEMO_MODE === "true";

async function api(path, body) {
  if (IS_PREVIEW)
    return path.startsWith("/automation")
      ? automationPreviewApi(path, body)
      : previewApi(path, body);
  const response = await fetch("/api" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = await response.text();
    try {
      message = JSON.parse(message).detail || message;
    } catch {}
    throw new Error(
      response.status === 401 ? "Authentication required" : message,
    );
  }
  return response.json();
}
const empty = {
  projects: [],
  tasks: [],
  events: [],
  runs: [],
  artifacts: [],
  running: false,
};
function App() {
  const [data, setData] = useState(empty),
    [auth, setAuth] = useState(false),
    [token, setToken] = useState(""),
    [error, setError] = useState(""),
    [modal, setModal] = useState(null),
    [tab, setTab] = useState("Overview"),
    [projectId, setProjectId] = useState(""),
    [selected, setSelected] = useState(null),
    [busy, setBusy] = useState(false),
    [tick, setTick] = useState(Date.now()),
    [surface, setSurface] = useState("platform");
  const refresh = async () => {
    try {
      setData(await api("/state"));
      setAuth(true);
    } catch (e) {
      if (e.message === "Authentication required") setAuth(false);
      else setError(e.message);
    }
  };
  useEffect(() => {
    refresh();
    const timer = setInterval(() => {
      refresh();
      setTick(Date.now());
    }, 2000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement;
    const onKey = (e) => {
      if (e.key === "Escape") setModal(null);
      if (e.key === "Tab") {
        const nodes = [
          ...document.querySelectorAll(
            ".modal button:not(:disabled), .modal input, .modal textarea, .modal select",
          ),
        ];
        if (!nodes.length) return;
        const first = nodes[0],
          last = nodes.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    document.querySelector(".modal input, .modal button")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [modal]);
  const action = async (path, body = {}) => {
    setBusy(true);
    try {
      await api(path, body);
      setError("");
      await refresh();
      setModal(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const project =
    data.projects.find((p) => p.id === projectId) || data.projects[0];
  const tasks = data.tasks.filter((t) => t.project_id === project?.id),
    m = metrics(tasks),
    active = tasks.find((t) => t.status === "running"),
    current =
      active ||
      tasks.find((t) => t.status === "blocked") ||
      tasks.find((t) => t.status === "queued" || t.status === "retry"),
    lastRun = data.runs.at(-1),
    checks = data.events.filter((e) => e.kind === "verification"),
    failures = checks.filter((e) => e.data.exit_code !== 0),
    elapsed = lastRun ? (lastRun.finished || tick / 1000) - lastRun.started : 0;
  const login = async (e) => {
    e.preventDefault();
    try {
      await api("/login", { token });
      setToken("");
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  };
  if (!auth)
    return (
      <div className="login">
        <div className="login-mark">
          h<span>·</span>
        </div>
        <p className="eyebrow">HIYO / AI AUTOMATION OS</p>
        <h1>
          Your business.
          <br />
          On autopilot.
        </h1>
        <p>One intelligence engine for every industry and department.</p>
        <form onSubmit={login}>
          <label htmlFor="token">Dashboard access token</label>
          <input
            id="token"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
            autoComplete="current-password"
            placeholder="Enter your local access token"
          />
          <button className="primary">
            Unlock command center <ArrowRight size={16} />
          </button>
        </form>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <small>
          <LockKeyhole size={13} /> Find your token in the controller’s
          dashboard-token file.
        </small>
      </div>
    );
  if (surface === "platform")
    return (
      <Platform
        api={api}
        preview={IS_PREVIEW}
        onEngineering={() => setSurface("engineering")}
        onLogout={() => action("/logout")}
      />
    );
  return (
    <div className="app">
      <button
        className="engineering-return"
        onClick={() => setSurface("platform")}
      >
        ← Back to Hiyo platform
      </button>
      <header>
        <a className="brand" href="#" onClick={() => setTab("Overview")}>
          h<span>·</span>
          <b>Hiyo</b>
          <i>ENGINEERING OS</i>
        </a>
        <nav aria-label="Main navigation">
          {["Overview", "Task queue", "Evidence", "Delivery"].map((t) => (
            <button
              key={t}
              className={tab === t ? "nav active" : "nav"}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </nav>
        <div className="header-right">
          <span className="private">
            <LockKeyhole size={13} />{" "}
            {IS_PREVIEW ? "UI preview" : "Private workspace"}
          </span>
          <button
            className="avatar"
            title={IS_PREVIEW ? "Browser preview" : "Sign out"}
            onClick={() => action("/logout")}
          >
            G
          </button>
        </div>
      </header>
      <main>
        {IS_PREVIEW && (
          <div className="preview-banner" role="status">
            <div>
              <b>Interactive UI preview</b>
              <span>
                Sample backlog · saved in your browser only · no Codex workers,
                tests, or billing run here.
              </span>
            </div>
            <a
              href="https://github.com/Ablelyf-Tech/hiyo#readme"
              target="_blank"
              rel="noreferrer"
            >
              Install the full controller <ArrowUpRight size={14} />
            </a>
          </div>
        )}
        <div className="page-heading">
          <div>
            <p className="eyebrow">
              COMMAND CENTER <span>/</span>{" "}
              {new Date(tick).toLocaleDateString(undefined, {
                day: "2-digit",
                month: "short",
                year: "numeric",
              })}
            </p>
            <h1>
              Built to keep moving<span>.</span>
            </h1>
            <p>
              From a business decision to working software. Every step,
              verified.
            </p>
          </div>
          <button className="outline" onClick={() => setModal("project")}>
            <Plus size={16} /> New project
          </button>
        </div>
        {error && (
          <div role="alert" className="error banner">
            {error}
            <button onClick={() => setError("")} aria-label="Dismiss error">
              <X size={16} />
            </button>
          </div>
        )}
        <div className="workspace-bar">
          <div className="workspace-name">
            <span className="project-icon">
              <Layers size={19} />
            </span>
            <div>
              <small>ACTIVE PROJECT</small>
              <select
                aria-label="Active project"
                value={project?.id || ""}
                onChange={(e) => setProjectId(e.target.value)}
              >
                {!project && <option value="">No project connected</option>}
                {data.projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="workspace-state">
            <span className={"dot " + (data.running ? "pulse" : "")} />
            {data.running
              ? "Autonomous execution"
              : data.stopped
                ? "Emergency stop active"
                : "Standing by"}
            <span className="divider" />
            <GitBranch size={14} />
            <span>{active ? "hiyo/" + active.id : "Local workspace"}</span>
          </div>
          <button
            className="icon-button"
            title="Runtime settings"
            onClick={() => setModal("settings")}
          >
            <Settings2 size={18} />
          </button>
        </div>
        {tab === "Overview" && (
          <>
            <div className="cockpit">
              <section className="panel journey">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">THE FLIGHT PLAN</p>
                    <h2>Decision to delivery</h2>
                  </div>
                  <span className="tag">{tasks.length} TASKS</span>
                </div>
                <div className="route-map">
                  <svg viewBox="0 0 360 280" aria-hidden="true">
                    <defs>
                      <pattern
                        id="grid"
                        width="32"
                        height="32"
                        patternUnits="userSpaceOnUse"
                      >
                        <path
                          d="M32 0H0V32"
                          fill="none"
                          stroke="#e2e2df"
                          strokeWidth="0.7"
                        />
                      </pattern>
                    </defs>
                    <rect width="360" height="280" fill="url(#grid)" />
                    <path
                      className="ghost-route"
                      d="M45 232C75 232 53 160 110 160S135 215 182 180S160 95 225 95S270 48 315 48"
                    />
                    <path
                      className="live-route"
                      strokeDasharray="500"
                      strokeDashoffset={500 - m.progress * 5}
                      d="M45 232C75 232 53 160 110 160S135 215 182 180S160 95 225 95S270 48 315 48"
                    />
                    <circle cx="45" cy="232" r="7" fill="#202220" />
                    <circle
                      cx="315"
                      cy="48"
                      r="7"
                      fill="#f4f4f1"
                      stroke="#232523"
                      strokeWidth="2"
                    />
                    <text x="28" y="263">
                      START / BRIEF
                    </text>
                    <text x="233" y="25">
                      VERIFIED RELEASE
                    </text>
                    <circle
                      cx={m.progress > 50 ? 225 : 110}
                      cy={m.progress > 50 ? 95 : 160}
                      r="16"
                      fill="#fff"
                      stroke="#c9cac5"
                    />
                    <path
                      d={
                        m.progress > 50 ? "M220 95l4 4 7-9" : "M105 160l4 4 7-9"
                      }
                      fill="none"
                      stroke="#222"
                      strokeWidth="2"
                    />
                  </svg>
                  <span className="map-label">
                    A clear path.
                    <br />
                    <b>Accountable at every turn.</b>
                  </span>
                </div>
                <div className="journey-footer">
                  <div>
                    <small>COMPLETED</small>
                    <strong>
                      {m.completed}
                      <em> / {tasks.length}</em>
                    </strong>
                  </div>
                  <ArrowRight size={21} />
                  <div>
                    <small>REMAINING</small>
                    <strong>
                      {m.remaining}
                      <em> tasks</em>
                    </strong>
                  </div>
                </div>
                <div className="progress">
                  <span style={{ width: m.progress + "%" }} />
                </div>
                <p className="caption">
                  Decision <ChevronRight /> Action <ChevronRight /> Outcome{" "}
                  <ChevronRight /> Proof
                </p>
              </section>
              <div className="middle">
                <section className="panel copilot">
                  <div className="panel-head">
                    <p className="eyebrow">AUTONOMOUS CONTROLLER</p>
                    <span className="tag">
                      <span className="dot" />{" "}
                      {data.running ? "RUNNING" : "IDLE"}
                    </span>
                  </div>
                  <div className={"orb " + (data.running ? "spinning" : "")}>
                    {Array.from({ length: 25 }, (_, i) => (
                      <i
                        key={i}
                        style={{
                          opacity: 0.15 + ((i * 7) % 10) / 12,
                          transform: `scale(${0.3 + ((i * 3) % 7) / 9})`,
                        }}
                      />
                    ))}
                  </div>
                  <h2>
                    {active
                      ? "Engineering in motion."
                      : current?.status === "blocked"
                        ? "A decision needs you."
                        : "What are we building next?"}
                  </h2>
                  <p>
                    {active
                      ? active.title
                      : current?.error ||
                        "Connect a project. Set the goal. Let your team take it from here."}
                  </p>
                  <button
                    className="text-button"
                    onClick={() => setModal(project ? "task" : "project")}
                  >
                    {project
                      ? "Add an engineering task"
                      : "Connect your first project"}{" "}
                    <ArrowUpRight size={14} />
                  </button>
                </section>
                <div className="tiles">
                  {roles.slice(0, 6).map((r, i) => (
                    <button
                      key={r}
                      className={
                        "worker-tile " +
                        (active?.stage === r ? "worker-active" : "")
                      }
                      onClick={() => {
                        setSelected(r);
                        setModal("worker");
                      }}
                    >
                      <span>
                        {
                          [
                            <Layers />,
                            <Box />,
                            <Terminal />,
                            <ShieldCheck />,
                            <Activity />,
                            <Search />,
                          ][i]
                        }
                      </span>
                      <b>{r}</b>
                      <small>
                        {active?.stage === r ? "Working" : "On standby"}
                      </small>
                    </button>
                  ))}
                </div>
              </div>
              <section className="panel autopilot">
                <div className="panel-head">
                  <p className="eyebrow">EXECUTION HEALTH</p>
                  <ShieldCheck size={18} />
                </div>
                <div className="speed">
                  <strong>
                    {m.progress}
                    <span>%</span>
                  </strong>
                  <p>mission complete</p>
                </div>
                <div className="engine-visual">
                  <div className="orbit orbit-one" />
                  <div className="orbit orbit-two" />
                  <div className="engine-core">
                    <Layers size={42} strokeWidth={1} />
                    <b>CODEX</b>
                    <small>ENGINE</small>
                  </div>
                  <span className="engine-node n1">PLAN</span>
                  <span className="engine-node n2">BUILD</span>
                  <span className="engine-node n3">VERIFY</span>
                  <span className="engine-node n4">DELIVER</span>
                </div>
                <div className="health-lines">
                  <div>
                    <span>Sandbox</span>
                    <b>
                      <LockKeyhole size={12} /> Required
                    </b>
                  </div>
                  <div>
                    <span>Human approvals</span>
                    <b>Required for sensitive actions</b>
                  </div>
                  <div>
                    <span>Execution mode</span>
                    <b>Sequential</b>
                  </div>
                </div>
                <div className="drive-modes">
                  <span className={!data.running ? "selected" : ""}>P</span>
                  <span className={data.running ? "selected" : ""}>D</span>
                  <span>S</span>
                  <span>M</span>
                </div>
                <div className="controls">
                  <button
                    className="primary"
                    disabled={
                      IS_PREVIEW || busy || data.running || !tasks.length
                    }
                    onClick={() => setModal("start")}
                  >
                    <Play size={15} fill="currentColor" /> Start autopilot
                  </button>
                  <button
                    className="stop-button"
                    onClick={() => action("/controller/stop")}
                    title="Emergency stop"
                    aria-label="Emergency stop"
                  >
                    <Square size={17} />
                  </button>
                </div>
                {data.stopped && (
                  <button
                    className="text-button"
                    disabled={data.running}
                    onClick={() => action("/controller/clear-stop")}
                  >
                    Clear emergency stop <RotateCcw size={13} />
                  </button>
                )}
              </section>
            </div>
            <div className="bottom-grid">
              <section className="panel current-task">
                <div className="panel-head">
                  <p className="eyebrow">NOW IN THE WORKSHOP</p>
                  <button
                    className="text-button"
                    onClick={() => setTab("Task queue")}
                  >
                    View queue <ArrowUpRight size={14} />
                  </button>
                </div>
                <div className="now">
                  <div className="terminal-icon">
                    <Terminal size={25} />
                  </div>
                  <div>
                    <h3>
                      {current?.title || "Your next big idea starts here"}
                    </h3>
                    <p>
                      {current
                        ? `${current.stage} · Attempt ${current.attempts} · ${current.status}`
                        : "Create a task with clear acceptance checks to begin."}
                    </p>
                  </div>
                  <span className="tag">
                    {current?.status || "READY WHEN YOU ARE"}
                  </span>
                </div>
              </section>
              <section className="panel telemetry">
                <div>
                  <Clock3 size={16} />
                  <small>RUNTIME</small>
                  <b>{duration(elapsed)}</b>
                </div>
                <div>
                  <Zap size={16} />
                  <small>RESERVED ESTIMATE</small>
                  <b>${(lastRun?.reserved || 0).toFixed(2)}</b>
                </div>
                <div>
                  <ShieldCheck size={16} />
                  <small>CHECKS RECORDED</small>
                  <b>
                    {checks.length}
                    <em> / {failures.length} failed</em>
                  </b>
                </div>
              </section>
            </div>
            <section className="activity-strip">
              <span className="dot" />
              <p>
                {data.events[0]
                  ? `${data.events[0].role} · ${data.events[0].kind} ${data.events[0].data.summary || data.events[0].data.reason || ""}`
                  : "System online. Waiting for your first engineering mission."}
              </p>
              <small>LIVE ACTIVITY</small>
            </section>
          </>
        )}
        {tab === "Task queue" && (
          <section className="panel detail-panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">EXECUTION BACKLOG</p>
                <h2>One verified step at a time.</h2>
              </div>
              <button
                className="primary"
                disabled={!project}
                onClick={() => setModal("task")}
              >
                <Plus size={16} /> Add task
              </button>
            </div>
            {!tasks.length && (
              <div className="empty-state">
                <Layers size={36} />
                <h3>No tasks yet</h3>
                <p>Define an outcome and the commands that prove it works.</p>
              </div>
            )}
            {tasks.map((t, i) => (
              <div className="task-row" key={t.id}>
                <span className="task-number">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <h3>{t.title}</h3>
                  <p>{t.spec}</p>
                  <code>{t.checks.map((c) => c.join(" ")).join(" · ")}</code>
                  {t.error && <p className="error">{t.error}</p>}
                </div>
                <span className="tag">{t.status}</span>
                {t.status === "blocked" && (
                  <button
                    className="outline"
                    onClick={() => action("/tasks/" + t.id + "/retry")}
                  >
                    Retry after inspection
                  </button>
                )}
              </div>
            ))}
          </section>
        )}
        {tab === "Evidence" && (
          <section className="panel detail-panel">
            <p className="eyebrow">OUTCOME → PROOF</p>
            <h2>The record speaks for itself.</h2>
            <p className="muted">
              Command exits, independent reviews, errors, and Git checkpoints.
              No invented results.
            </p>
            {!data.events.length && (
              <div className="empty-state">
                <ShieldCheck size={36} />
                <h3>No evidence recorded yet</h3>
              </div>
            )}
            {data.events.map((e) => (
              <details key={e.seq} className="event">
                <summary>
                  <span className="tag">{e.role}</span>
                  <b>{e.kind}</b>
                  <time>{new Date(e.created * 1000).toLocaleTimeString()}</time>
                </summary>
                <pre>{JSON.stringify(e.data, null, 2)}</pre>
              </details>
            ))}
          </section>
        )}
        {tab === "Delivery" && (
          <section className="panel detail-panel">
            <p className="eyebrow">DELIVERY BAY</p>
            <h2>Working software. With receipts.</h2>
            <p className="muted">
              Verified source archives, test reports, and release notes appear
              here after completion.
            </p>
            <div className="artifact-grid">
              {data.artifacts.map((name) => (
                <a
                  key={name}
                  className="artifact"
                  href={
                    "/api/artifacts/" +
                    name.split("/").map(encodeURIComponent).join("/")
                  }
                  download
                >
                  <FileText size={25} />
                  <b>{name.split("/").at(-1)}</b>
                  <small>{name.split("/")[0]}</small>
                  <Download size={16} />
                </a>
              ))}
            </div>
            {!data.artifacts.length && (
              <div className="empty-state">
                <Box size={40} />
                <h3>Nothing released yet</h3>
                <p>
                  Only tasks that pass acceptance checks and review reach this
                  bay.
                </p>
              </div>
            )}
            {tasks
              .filter((t) => t.checkpoint)
              .map((t) => (
                <p key={t.id}>
                  <GitBranch size={14} /> {t.title}{" "}
                  <code>{t.checkpoint.slice(0, 12)}</code>
                </p>
              ))}
          </section>
        )}
        <footer>
          <b>
            Hiyo<span>·</span>
          </b>
          <span>DECIDE. BUILD. PROVE.</span>
          <button className="text-button" onClick={() => setModal("help")}>
            <CircleHelp size={14} /> Operating guide
          </button>
        </footer>
      </main>
      {modal && (
        <div
          className="modal-backdrop"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setModal(null);
          }}
        >
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={modal + " dialog"}
          >
            <button
              className="close"
              onClick={() => setModal(null)}
              aria-label="Close dialog"
            >
              <X size={20} />
            </button>
            {modal === "project" && (
              <>
                <p className="eyebrow">NEW MISSION</p>
                <h2>Connect a project</h2>
                <p>
                  Use an existing, trusted Git repository with an initial
                  commit. Controller state stays outside your project.
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.target);
                    action("/projects", Object.fromEntries(f));
                  }}
                >
                  <label>
                    Project name
                    <input name="name" required placeholder="Customer portal" />
                  </label>
                  <label>
                    Business goal
                    <textarea
                      name="brief"
                      required
                      minLength={10}
                      placeholder="What outcome should this product create?"
                    />
                  </label>
                  <label>
                    Workspace folder
                    <input
                      name="workspace"
                      required
                      placeholder="customer-portal"
                    />
                  </label>
                  <small>Relative to {data.projects_root}</small>
                  <button className="primary" disabled={busy}>
                    Connect project <ArrowRight size={16} />
                  </button>
                </form>
              </>
            )}
            {modal === "task" && (
              <>
                <p className="eyebrow">DECISION → ACTION</p>
                <h2>Define the next outcome</h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.target);
                    let checks;
                    try {
                      checks = JSON.parse(f.get("checks"));
                    } catch {
                      setError("Checks must be a JSON array of command arrays");
                      return;
                    }
                    action("/projects/" + project.id + "/tasks", {
                      title: f.get("title"),
                      spec: f.get("spec"),
                      checks,
                      priority: Number(f.get("priority")),
                    });
                  }}
                >
                  <label>
                    Task title
                    <input
                      name="title"
                      required
                      placeholder="Build the onboarding flow"
                    />
                  </label>
                  <label>
                    Acceptance criteria
                    <textarea
                      name="spec"
                      minLength={10}
                      required
                      placeholder="Describe observable behavior, edge cases, and required documentation."
                    />
                  </label>
                  <label>
                    Acceptance commands (JSON argv arrays)
                    <textarea
                      name="checks"
                      required
                      defaultValue={'[["python", "-m", "pytest"]]'}
                    />
                  </label>
                  <p className="form-note">
                    These commands execute locally with your permissions.
                    Approve only trusted tests and builds. Codex cannot edit
                    this acceptance command list.
                  </p>
                  <label>
                    Priority
                    <select name="priority">
                      <option value="0">Normal</option>
                      <option value="50">High</option>
                      <option value="100">Critical</option>
                    </select>
                  </label>
                  <button className="primary" disabled={busy}>
                    Approve and queue task <Plus size={16} />
                  </button>
                </form>
              </>
            )}
            {(modal === "start" || modal === "settings") && (
              <>
                <p className="eyebrow">AUTOPILOT LIMITS</p>
                <h2>Bounded by design.</h2>
                <p>
                  Each task runs through planning, architecture, implementation,
                  tests, review, and delivery. Production actions always need a
                  separate human decision.
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.target);
                    action("/controller/start", {
                      approve_codex_usage: true,
                      max_seconds: Number(f.get("minutes")) * 60,
                      max_calls: Number(f.get("calls")),
                      estimated_budget: Number(f.get("budget")),
                      reserve_per_call: Number(f.get("reserve")),
                    });
                  }}
                >
                  <div className="form-grid">
                    <label>
                      Runtime (minutes)
                      <input
                        name="minutes"
                        type="number"
                        min="1"
                        max="1440"
                        defaultValue="60"
                        required
                      />
                    </label>
                    <label>
                      Maximum model calls
                      <input
                        name="calls"
                        type="number"
                        min="1"
                        max="500"
                        defaultValue="20"
                        required
                      />
                    </label>
                    <label>
                      Estimated budget ($)
                      <input
                        name="budget"
                        type="number"
                        min="0.01"
                        max="1000"
                        step="0.01"
                        defaultValue="5"
                        required
                      />
                    </label>
                    <label>
                      Reserve per call ($)
                      <input
                        name="reserve"
                        type="number"
                        min="0.01"
                        max="100"
                        step="0.01"
                        defaultValue="0.25"
                        required
                      />
                    </label>
                  </div>
                  <p className="form-note">
                    Budget is a planning estimate, not a provider billing cap.
                    Configure a provider spending cap separately. This
                    authorizes Codex usage within these execution limits.
                  </p>
                  <label className="checkbox">
                    <input type="checkbox" required /> I approve Codex usage and
                    have reviewed this workspace and its acceptance commands.
                  </label>
                  <button
                    className="primary"
                    disabled={
                      IS_PREVIEW ||
                      busy ||
                      data.running ||
                      data.stopped ||
                      !tasks.length
                    }
                  >
                    Start approved backlog <Play size={16} />
                  </button>
                </form>
              </>
            )}
            {modal === "worker" && (
              <>
                <p className="eyebrow">ENGINEERING TEAM</p>
                <h2>{selected}</h2>
                <p>
                  {
                    {
                      Planner:
                        "Inspects the product brief, repository, dependencies, and ordered implementation steps.",
                      Architect:
                        "Defines architecture, data models, interfaces, and security boundaries.",
                      Builder:
                        "Implements source, tests, integrations, migrations, and operating documentation.",
                      Tester:
                        "Runs the human-approved acceptance commands independently of the model’s claims.",
                      Debugger:
                        "Uses actual command failures to repair implementation, then reruns verification.",
                      Reviewer:
                        "Runs in a separate read-only Codex invocation and checks the final diff for regressions and security.",
                    }[selected]
                  }
                </p>
                <span className="tag">
                  {active?.stage === selected ? "WORKING" : "ON STANDBY"}
                </span>
              </>
            )}
            {modal === "help" && (
              <>
                <p className="eyebrow">OPERATING GUIDE</p>
                <h2>You set the destination.</h2>
                <ol>
                  <li>
                    Connect a trusted Git workspace under the configured
                    projects directory.
                  </li>
                  <li>
                    Add tasks with explicit acceptance criteria and
                    noninteractive test commands, or import a dependency-ordered
                    JSON plan using the CLI.
                  </li>
                  <li>
                    Approve Codex usage and set runtime, call, and estimated
                    budget limits.
                  </li>
                  <li>
                    Monitor live evidence. Emergency stop terminates active
                    subprocesses.
                  </li>
                  <li>
                    Inspect blockers and dirty workspaces before retrying.
                    Download verified artifacts from Delivery.
                  </li>
                </ol>
                <p>
                  Autopilot never pushes or deploys. Windows installation and
                  Task Scheduler instructions are included in the repository.
                </p>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")).render(
  import.meta.env.VITE_CLOUD_MODE === "true" ? (
    <React.Suspense fallback={<p>Loading Hiyo…</p>}>
      <CloudShell />
    </React.Suspense>
  ) : (
    <App />
  ),
);
