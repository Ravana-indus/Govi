import { useEffect, useState } from "react";
import { api, clearToken, setToken } from "../api.js";
import { useT } from "../i18n.js";

const SUBS = ["KB", "Settings", "Analytics", "Data"];

export default function AdminConsole() {
  const t = useT();
  const [authed, setAuthed] = useState(!!localStorage.getItem("farmingos_token"));
  const [email, setEmail] = useState("admin@farmingos.lk");
  const [password, setPassword] = useState("admin123");
  const [err, setErr] = useState("");
  const [sub, setSub] = useState("KB");

  async function login() {
    setErr("");
    try { const r = await api.staffLogin(email, password); setToken(r.access_token); setAuthed(true); }
    catch (e) { setErr(e.message); }
  }

  if (!authed) {
    return (
      <div className="card">
        <h2>{t("admin")} · {t("login")}</h2>
        <label>{t("email")}</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>{t("password")}</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="btn" onClick={login}>{t("login")}</button>
        <p className="muted">Demo: admin@farmingos.lk / admin123</p>
        {err && <div className="error">{err}</div>}
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: ".5rem" }}>
          <h2 style={{ margin: 0 }}>Admin / Knowledge Base</h2>
          <button className="btn ghost" style={{ marginLeft: "auto", marginTop: 0 }}
                  onClick={() => { clearToken(); setAuthed(false); }}>Log out</button>
        </div>
        <div className="chips" style={{ marginTop: ".7rem" }}>
          {SUBS.map((s) => (
            <span key={s} className="chip" style={s === sub ? { background: "#e3f4e9", borderColor: "#1b7a3e", fontWeight: 600 } : {}}
                  onClick={() => setSub(s)}>{s}</span>
          ))}
        </div>
      </div>
      {sub === "KB" && <KB />}
      {sub === "Settings" && <Settings />}
      {sub === "Analytics" && <Analytics />}
      {sub === "Data" && <Data />}
    </>
  );
}

function KB() {
  const [docs, setDocs] = useState([]);
  const [crops, setCrops] = useState([]);
  const [form, setForm] = useState({ title: "", topic: "disease", crop_id: "", body: "Steps:\n1. ", status: "validated" });
  const [msg, setMsg] = useState("");

  async function load() {
    setDocs(await api.kbDocs());
    if (!crops.length) setCrops(await api.crops());
  }
  useEffect(() => { load(); }, []);

  async function create() {
    setMsg("");
    try {
      await api.kbCreate({ ...form, crop_id: form.crop_id || null });
      setMsg("✓ doc created" + (form.status === "validated" ? " & indexed" : ""));
      setForm({ ...form, title: "", body: "Steps:\n1. " });
      load();
    } catch (e) { setMsg("⚠ " + e.message); }
  }
  async function validate(d) { await api.kbPatch(d.id, { status: "validated" }); load(); }
  async function reindex(d) { const r = await api.kbReindex(d.id); setMsg(`✓ reindexed ${r.chunks} chunks`); }

  return (
    <>
      <div className="card">
        <h2>Knowledge documents</h2>
        <table>
          <thead><tr><th>Title</th><th>Topic</th><th>Status</th><th>v</th><th></th></tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td>{d.title}</td><td>{d.topic}</td>
                <td><span className={`pill ${d.status === "validated" ? "reco" : "warn"}`}>{d.status}</span></td>
                <td>{d.version}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {d.status !== "validated" && <button className="btn sm" onClick={() => validate(d)}>Validate</button>}{" "}
                  <button className="btn sm ghost" onClick={() => reindex(d)}>Reindex</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2>New document</h2>
        <label>Title</label>
        <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <div className="row">
          <div><label>Topic</label>
            <select value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })}>
              {["disease", "pest", "fertilizer", "calendar", "subsidy", "general"].map((x) => <option key={x}>{x}</option>)}
            </select>
          </div>
          <div><label>Crop (optional)</label>
            <select value={form.crop_id} onChange={(e) => setForm({ ...form, crop_id: e.target.value })}>
              <option value="">—</option>
              {crops.map((c) => <option key={c.id} value={c.id}>{c.name_en}</option>)}
            </select>
          </div>
        </div>
        <label>Body (use "Steps:" and "Inputs:" sections)</label>
        <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })}
                  style={{ width: "100%", minHeight: 120, padding: ".6rem", borderRadius: 9, border: "1px solid var(--line)", font: "inherit" }} />
        <label style={{ display: "flex", gap: ".5rem", alignItems: "center", marginTop: ".6rem" }}>
          <input type="checkbox" checked={form.status === "validated"} style={{ width: "auto" }}
                 onChange={(e) => setForm({ ...form, status: e.target.checked ? "validated" : "draft" })} />
          <span>Validated (retrievable by Crop Doctor)</span>
        </label>
        <button className="btn" onClick={create} disabled={!form.title}>Create</button>
        {msg && <div className="flash">{msg}</div>}
      </div>
    </>
  );
}

function Settings() {
  const [s, setS] = useState(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { api.getSettings().then(setS); }, []);
  if (!s) return <div className="card">Loading…</div>;
  async function save() {
    const r = await api.patchSettings({
      crop_confidence_threshold: Number(s.crop_confidence_threshold),
      assisted_mode: !!s.assisted_mode, price_stale_days: Number(s.price_stale_days),
    });
    setS(r); setMsg("✓ saved — agents pick this up immediately");
  }
  return (
    <div className="card">
      <h2>Feature flags</h2>
      <label>Crop Doctor confidence threshold: <b>{Number(s.crop_confidence_threshold).toFixed(2)}</b></label>
      <input type="range" min="0.3" max="0.95" step="0.05" value={s.crop_confidence_threshold}
             onChange={(e) => setS({ ...s, crop_confidence_threshold: e.target.value })} />
      <p className="muted">Below this, a diagnosis escalates to an officer instead of advising.</p>
      <label style={{ display: "flex", gap: ".5rem", alignItems: "center" }}>
        <input type="checkbox" checked={!!s.assisted_mode} style={{ width: "auto" }}
               onChange={(e) => setS({ ...s, assisted_mode: e.target.checked })} />
        <span>Assisted mode (officer fronts every AI answer — for the pilot)</span>
      </label>
      <label>Price staleness (days) before confidence drops</label>
      <input type="number" value={s.price_stale_days} onChange={(e) => setS({ ...s, price_stale_days: e.target.value })} />
      <button className="btn" onClick={save}>Save flags</button>
      {msg && <div className="flash">{msg}</div>}
    </div>
  );
}

function Analytics() {
  const [ns, setNs] = useState(null), [u, setU] = useState(null), [d, setD] = useState(null);
  useEffect(() => { api.northstar().then(setNs); api.usage().then(setU); api.dashboard().then(setD).catch(() => {}); }, []);
  const Card = ({ k, v }) => (
    <div style={{ flex: 1, background: "#f4f7f2", borderRadius: 10, padding: ".7rem", textAlign: "center" }}>
      <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--green-d)" }}>{v}</div>
      <div className="muted">{k}</div>
    </div>
  );
  return (
    <div className="card">
      <h2>North-star &amp; usage</h2>
      {ns && <div className="row" style={{ marginBottom: ".6rem" }}>
        <Card k="advised" v={ns.advised} /><Card k="acted %" v={ns.acted_pct + "%"} /><Card k="outcome %" v={ns.outcome_pct + "%"} />
      </div>}
      {u && <div className="row">
        <Card k="conversations" v={u.conversations} /><Card k="messages" v={u.messages} /><Card k="open escalations" v={u.open_escalations} />
      </div>}
      {d && (
        <div style={{ marginTop: ".8rem" }}>
          <b>Conversations by intent</b>
          <table><tbody>
            {Object.entries(d.by_intent).map(([k, v]) => (
              <tr key={k}><td>{k}</td><td style={{ textAlign: "right" }}>{v}</td></tr>
            ))}
          </tbody></table>
          <p className="muted">Escalations overdue (SLA): <b>{d.sla_overdue}</b></p>
        </div>
      )}
      <p className="muted" style={{ marginTop: ".6rem" }}>North-star = % of advised farmers who acted and saw an outcome.</p>
    </div>
  );
}

function Data() {
  const [farmers, setFarmers] = useState([]), [convos, setConvos] = useState([]);
  useEffect(() => { api.adminFarmers().then(setFarmers); api.adminConversations().then(setConvos); }, []);
  return (
    <>
      <div className="card">
        <h2>Farmers ({farmers.length})</h2>
        <table><thead><tr><th>Phone</th><th>District</th><th>Lang</th><th>Via</th></tr></thead>
          <tbody>{farmers.slice(0, 12).map((f) => (
            <tr key={f.id}><td>{f.phone}</td><td>{f.district || "—"}</td><td>{f.preferred_language}</td><td>{f.created_via}</td></tr>
          ))}</tbody></table>
      </div>
      <div className="card">
        <h2>Recent conversations ({convos.length})</h2>
        <table><thead><tr><th>Farmer</th><th>Channel</th><th>Last intent</th></tr></thead>
          <tbody>{convos.slice(0, 12).map((c) => (
            <tr key={c.id}><td>{c.farmer_phone}</td><td>{c.channel}</td><td>{c.last_intent || "—"}</td></tr>
          ))}</tbody></table>
      </div>
    </>
  );
}
