import { useState } from "react";
import { api, clearToken } from "../api.js";
import { useT } from "../i18n.js";

// PDPA (Sri Lanka PDPA No. 9 of 2022): data access + right to erasure.
export default function Privacy() {
  const t = useT();
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const authed = !!localStorage.getItem("farmingos_token");

  async function exportData() {
    setErr(""); setMsg("");
    try { setData(await api.exportData()); }
    catch (e) { setErr(e.message); }
  }

  function download() {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "my-farmingos-data.json";
    a.click();
  }

  async function erase() {
    if (!confirm("Delete all your personal data? This cannot be undone.")) return;
    setErr(""); setMsg("");
    try {
      await api.eraseData();
      setMsg("Your personal data has been erased. Logging you out.");
      setData(null);
      setTimeout(() => { clearToken(); localStorage.removeItem("farmingos_phone"); }, 1500);
    } catch (e) { setErr(e.message); }
  }

  return (
    <div className="card">
      <h2>{t("privacy")}</h2>
      <p className="muted">
        Your data is yours (Sri Lanka PDPA, 2022). Download everything we hold, or
        ask us to erase your personal information permanently.
      </p>
      {!authed && <p className="muted">Complete onboarding first.</p>}
      <div className="row" style={{ marginTop: ".6rem" }}>
        <button className="btn" onClick={exportData} disabled={!authed}>Download my data</button>
        <button className="btn" style={{ background: "var(--danger)" }} onClick={erase} disabled={!authed}>
          Delete my data
        </button>
      </div>
      {msg && <div className="flash">{msg}</div>}
      {err && <div className="error">{err}</div>}
      {data && (
        <div style={{ marginTop: ".8rem" }}>
          <button className="btn ghost" onClick={download}>Save as JSON</button>
          <pre style={{ background: "#f4f7f2", borderRadius: 8, padding: ".7rem",
                        overflow: "auto", maxHeight: 280, fontSize: ".75rem" }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
