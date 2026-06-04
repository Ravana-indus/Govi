import { useEffect, useState } from "react";
import { api, clearToken, setToken } from "../api.js";
import { useT } from "../i18n.js";

export default function PricePortal() {
  const t = useT();
  const [authed, setAuthed] = useState(!!localStorage.getItem("farmingos_token"));
  const [email, setEmail] = useState("staff@farmingos.lk");
  const [password, setPassword] = useState("ground123");
  const [err, setErr] = useState("");

  const [crops, setCrops] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [form, setForm] = useState({ market_id: "", crop_id: "", price_min: "", price_max: "" });
  const [coverage, setCoverage] = useState(null);
  const [flash, setFlash] = useState("");

  async function login() {
    setErr("");
    try {
      const r = await api.staffLogin(email, password);
      setToken(r.access_token); setAuthed(true);
    } catch (e) { setErr(e.message); }
  }
  function logout() { clearToken(); setAuthed(false); }

  async function refresh() {
    const [c, m] = await Promise.all([api.crops(), api.markets()]);
    setCrops(c); setMarkets(m);
    setForm((f) => ({ ...f, market_id: m[0]?.id || "", crop_id: c[0]?.id || "" }));
    try { setCoverage(await api.coverage()); } catch { /* role may lack access */ }
  }
  useEffect(() => { if (authed) refresh(); }, [authed]);

  async function savePrice() {
    setFlash(""); setErr("");
    try {
      await api.addPrice({
        ...form, price_min: Number(form.price_min), price_max: Number(form.price_max),
        observed_date: new Date().toISOString().slice(0, 10),
      });
      setFlash("✓ saved");
      setForm((f) => ({ ...f, price_min: "", price_max: "" }));
      setCoverage(await api.coverage());
    } catch (e) { setErr(e.message); }
  }

  async function bulk(e) {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const r = await api.bulkPrices(file);
      setFlash(`✓ ${r.created} rows, ${r.errors.length} errors`);
      setCoverage(await api.coverage());
    } catch (e2) { setErr(e2.message); }
    e.target.value = "";
  }

  if (!authed) {
    return (
      <div className="card">
        <h2>{t("pricePortal")} · {t("login")}</h2>
        <label>{t("email")}</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>{t("password")}</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="btn" onClick={login}>{t("login")}</button>
        <p className="muted">Demo: staff@farmingos.lk / ground123</p>
        {err && <div className="error">{err}</div>}
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <div style={{ display: "flex", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>{t("priceEntry")}</h2>
          <button className="btn ghost" style={{ marginLeft: "auto", marginTop: 0 }} onClick={logout}>×</button>
        </div>
        <div className="row">
          <div>
            <label>{t("market")}</label>
            <select value={form.market_id} onChange={(e) => setForm({ ...form, market_id: e.target.value })}>
              {markets.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </div>
          <div>
            <label>{t("crop")}</label>
            <select value={form.crop_id} onChange={(e) => setForm({ ...form, crop_id: e.target.value })}>
              {crops.map((c) => <option key={c.id} value={c.id}>{c.name_en}</option>)}
            </select>
          </div>
        </div>
        <div className="row">
          <div>
            <label>{t("min")}</label>
            <input type="number" value={form.price_min} onChange={(e) => setForm({ ...form, price_min: e.target.value })} />
          </div>
          <div>
            <label>{t("max")}</label>
            <input type="number" value={form.price_max} onChange={(e) => setForm({ ...form, price_max: e.target.value })} />
          </div>
        </div>
        <button className="btn" onClick={savePrice} disabled={!form.price_min || !form.price_max}>{t("save")}</button>
        <label style={{ marginTop: "1rem" }}>{t("bulkUpload")}</label>
        <input type="file" accept=".csv" onChange={bulk} />
        <p className="muted">CSV: market_id,crop_id,price_min,price_max,observed_date</p>
        {flash && <div className="muted" style={{ color: "var(--green)" }}>{flash}</div>}
        {err && <div className="error">{err}</div>}
      </div>

      {coverage && (
        <div className="card">
          <h2>{t("coverage")} · {coverage.date}</h2>
          <div className="bar"><i style={{ width: `${coverage.coverage_pct}%` }} /></div>
          <p className="muted">{coverage.coverage_pct}% — {coverage.covered}/{coverage.total} market×crop cells filled today</p>
          {coverage.missing?.length > 0 && (
            <table>
              <thead><tr><th>{t("market")}</th><th>{t("crop")}</th></tr></thead>
              <tbody>
                {coverage.missing.slice(0, 8).map((x, i) => (
                  <tr key={i}><td>{x.market}</td><td>{x.crop}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </>
  );
}
