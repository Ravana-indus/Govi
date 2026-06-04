import { useEffect, useState } from "react";
import { api, clearToken, setToken } from "../api.js";
import { useT } from "../i18n.js";

export default function OfficerConsole() {
  const t = useT();
  const [authed, setAuthed] = useState(!!localStorage.getItem("farmingos_token"));
  const [email, setEmail] = useState("officer@farmingos.lk");
  const [password, setPassword] = useState("officer123");
  const [err, setErr] = useState("");
  const [items, setItems] = useState([]);
  const [flash, setFlash] = useState("");

  async function login() {
    setErr("");
    try { const r = await api.staffLogin(email, password); setToken(r.access_token); setAuthed(true); }
    catch (e) { setErr(e.message); }
  }
  async function load() {
    try {
      const open = await api.escalations("open");
      const claimed = await api.escalations("claimed");
      setItems([...claimed, ...open]);
    } catch (e) { setErr(e.message); }
  }
  useEffect(() => { if (authed) load(); }, [authed]);

  if (!authed) {
    return (
      <div className="card">
        <h2>{t("officer")} · {t("login")}</h2>
        <label>{t("email")}</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>{t("password")}</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="btn" onClick={login}>{t("login")}</button>
        <p className="muted">Demo: officer@farmingos.lk / officer123</p>
        {err && <div className="error">{err}</div>}
      </div>
    );
  }

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Escalation queue</h2>
        <button className="btn ghost" style={{ marginLeft: "auto", marginTop: 0 }}
                onClick={() => { clearToken(); setAuthed(false); }}>Log out</button>
      </div>
      {flash && <div className="flash">{flash}</div>}
      {items.length === 0 && <p className="muted">No open escalations. Assisted-mode answers and low-confidence diagnoses land here.</p>}
      {items.map((e) => (
        <EscalationCard key={e.id} esc={e} onChange={(m) => { setFlash(m); load(); }} />
      ))}
    </div>
  );
}

function EscalationCard({ esc, onChange }) {
  const [note, setNote] = useState(esc.ai_draft || "");
  const [logOutcome, setLogOutcome] = useState(true);

  async function claim() { await api.escalationClaim(esc.id); onChange("✓ claimed"); }
  async function resolve() {
    await api.escalationResolve(esc.id, note);
    if (logOutcome) {
      await api.logOutcome({ farmer_id: esc.farmer_id, recommended_action: note.slice(0, 80),
                             action_taken: true });
    }
    onChange("✓ resolved" + (logOutcome ? " & outcome logged" : ""));
  }

  return (
    <div className="esc">
      <div>
        <b>{esc.type.toUpperCase()}</b> · {esc.reason}{" "}
        <span className={`pill ${esc.status === "open" ? "warn" : "reco"}`}>{esc.status}</span>
      </div>
      {esc.ai_draft && (
        <>
          <label style={{ marginTop: ".4rem" }}>AI draft (edit before approving)</label>
          <textarea value={note} onChange={(e) => setNote(e.target.value)}
                    style={{ width: "100%", minHeight: 80, padding: ".5rem", borderRadius: 8,
                             border: "1px solid var(--line)", font: "inherit" }} />
        </>
      )}
      {!esc.ai_draft && (
        <>
          <label style={{ marginTop: ".4rem" }}>Resolution note</label>
          <input value={note} onChange={(e) => setNote(e.target.value)}
                 placeholder="What you advised the farmer…" />
        </>
      )}
      <label style={{ display: "flex", gap: ".4rem", alignItems: "center", marginTop: ".5rem" }}>
        <input type="checkbox" checked={logOutcome} style={{ width: "auto" }}
               onChange={(e) => setLogOutcome(e.target.checked)} />
        <span className="muted">Log outcome (feeds north-star)</span>
      </label>
      <div style={{ marginTop: ".5rem" }}>
        {esc.status === "open" && <button className="btn sm amber" onClick={claim}>Claim</button>}{" "}
        <button className="btn sm" onClick={resolve} disabled={!note}>Resolve</button>
      </div>
    </div>
  );
}
