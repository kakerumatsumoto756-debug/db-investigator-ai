import { FormEvent, useEffect, useState } from "react";

import {
  ActivityEvent,
  DatabaseStatus,
  getDatabaseStatus,
  getInvestigation,
  Investigation,
  InvestigationReport,
  startInvestigation
} from "./api";

const EXAMPLE_SQL = `SELECT id, status, total_cents, created_at
FROM orders
WHERE user_id = 1544
ORDER BY created_at DESC
LIMIT 25;`;

function StatusBadge({ database }: { database: DatabaseStatus | null }) {
  const connected = database?.connected === true;
  return (
    <div className={`status-badge ${connected ? "connected" : "disconnected"}`}>
      <span className="status-dot" />
      <div>
        <strong>{connected ? "PostgreSQL connected" : "Database unavailable"}</strong>
        <span>{connected ? database?.version?.split(",")[0] : database?.error ?? "Checking…"}</span>
      </div>
    </div>
  );
}

function Timeline({ events, status }: { events: ActivityEvent[]; status?: string }) {
  if (!events.length) {
    return (
      <div className="empty-state">
        <span className="empty-icon">⌁</span>
        <strong>No investigation running</strong>
        <p>Agent actions and observed evidence will appear here.</p>
      </div>
    );
  }

  return (
    <ol className="timeline">
      {events.map((event) => (
        <li key={event.sequence}>
          <span className="timeline-marker" />
          <div className="event-card">
            <div className="event-meta">
              <span>{event.kind.replaceAll("_", " ")}</span>
              <time>{new Date(event.created_at).toLocaleTimeString()}</time>
            </div>
            <p>{event.summary}</p>
            {event.result_preview && (
              <details>
                <summary>{event.tool_name ?? "View tool result"}</summary>
                <pre>{JSON.stringify(event.result_preview, null, 2)}</pre>
              </details>
            )}
          </div>
        </li>
      ))}
      {status === "running" && (
        <li className="working-event">
          <span className="timeline-marker pulse" />
          <div className="event-card muted">Waiting for the agent’s next action…</div>
        </li>
      )}
    </ol>
  );
}

function ListSection({ title, values }: { title: string; values: string[] }) {
  return (
    <section className="report-section">
      <h3>{title}</h3>
      {values.length ? (
        <ul>{values.map((value, index) => <li key={`${title}-${index}`}>{value}</li>)}</ul>
      ) : (
        <p className="muted">No observed comparison is available.</p>
      )}
    </section>
  );
}

function Report({ report }: { report: InvestigationReport }) {
  return (
    <div className="report">
      <div className="report-heading">
        <div>
          <span className="eyebrow">Investigation complete</span>
          <h2>Evidence-backed report</h2>
        </div>
        <div className="confidence">
          <span>Confidence</span>
          <strong>{Math.round(report.confidence * 100)}%</strong>
        </div>
      </div>
      <section className="report-section"><h3>Problem</h3><p>{report.problem}</p></section>
      <ListSection title="Evidence" values={report.evidence} />
      <section className="report-section accent">
        <h3>Root-cause hypothesis</h3><p>{report.root_cause_hypothesis}</p>
      </section>
      <section className="report-section"><h3>Recommended change</h3><p>{report.recommended_change}</p></section>
      <ListSection title="Before / after evidence" values={report.before_after_evidence} />
      <ListSection title="Risks" values={report.risks} />
      {report.sql_recommendation && (
        <section className="report-section">
          <h3>SQL recommendation</h3><pre className="sql-output">{report.sql_recommendation}</pre>
        </section>
      )}
    </div>
  );
}

export default function App() {
  const [database, setDatabase] = useState<DatabaseStatus | null>(null);
  const [problem, setProblem] = useState("Customer order history is slow as the table grows.");
  const [sql, setSql] = useState(EXAMPLE_SQL);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = investigation?.status === "queued" || investigation?.status === "running";

  useEffect(() => {
    getDatabaseStatus().then(setDatabase).catch((reason: Error) => {
      setDatabase({ connected: false, version: null, error: reason.message });
    });
  }, []);

  useEffect(() => {
    if (!investigation || !busy) return;
    const timer = window.setTimeout(() => {
      getInvestigation(investigation.id).then(setInvestigation).catch((reason: Error) => {
        setError(reason.message);
      });
    }, 900);
    return () => window.clearTimeout(timer);
  }, [investigation, busy]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      setInvestigation(await startInvestigation(problem, sql));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start the investigation");
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="DB Investigator AI home">
          <span className="brand-mark">DB</span>
          <span><strong>Investigator</strong><small>AI</small></span>
        </a>
        <StatusBadge database={database} />
      </header>

      <main>
        <section className="hero">
          <span className="eyebrow">PostgreSQL diagnostics</span>
          <h1>Investigate query problems<br />from evidence.</h1>
          <p>Submit a symptom, a SQL query, or both. The agent inspects the database, tests hypotheses, and reports what it actually observes.</p>
        </section>

        <div className="workspace-grid">
          <section className="panel input-panel">
            <div className="panel-heading"><span>01</span><div><h2>Investigation input</h2><p>Describe the behavior you want examined.</p></div></div>
            <form onSubmit={submit}>
              <label htmlFor="problem">Problem description</label>
              <textarea id="problem" value={problem} onChange={(event) => setProblem(event.target.value)} rows={4} maxLength={10000} placeholder="What is slow, incorrect, or unexpected?" />
              <div className="label-row"><label htmlFor="sql">SQL query</label><span>Optional</span></div>
              <textarea id="sql" className="code-input" value={sql} onChange={(event) => setSql(event.target.value)} rows={10} maxLength={100000} placeholder="SELECT …" spellCheck={false} />
              {error && <div className="error-banner">{error}</div>}
              {investigation?.error && <div className="error-banner">{investigation.error}</div>}
              <button type="submit" disabled={busy || (!problem.trim() && !sql.trim())}>
                <span>{busy ? "Investigating…" : "Investigate"}</span><span aria-hidden>→</span>
              </button>
              <p className="safety-note"><span>◆</span> Read-only tools · statement timeout · bounded results</p>
            </form>
          </section>

          <section className="panel activity-panel">
            <div className="panel-heading"><span>02</span><div><h2>Agent activity</h2><p>Actions and tool output, without hidden reasoning.</p></div></div>
            <Timeline events={investigation?.events ?? []} status={investigation?.status} />
          </section>
        </div>

        <section className="report-container">
          {investigation?.report ? <Report report={investigation.report} /> : (
            <div className="report-placeholder"><span>03</span><div><h2>Investigation report</h2><p>The final diagnosis, observed evidence, recommendation, validation, and risks will appear here.</p></div></div>
          )}
        </section>
      </main>
      <footer><span>DB Investigator AI</span><span>Evidence over intuition</span></footer>
    </div>
  );
}

