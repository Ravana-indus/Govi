import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api.js";
import { LangContext, useT } from "../i18n.js";
import { useContext } from "react";

const DISTRICTS = ["Matale", "Kandy", "Nuwara Eliya", "Anuradhapura", "Badulla", "Colombo"];

export default function Onboarding() {
  const t = useT();
  const { lang } = useContext(LangContext);
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [devOtp, setDevOtp] = useState(null);
  const [district, setDistrict] = useState("Matale");
  const [consent, setConsent] = useState(true);
  const [crops, setCrops] = useState([]);
  const [allCrops, setAllCrops] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => { api.crops().then(setAllCrops).catch(() => {}); }, []);

  async function sendOtp() {
    setErr("");
    try {
      const r = await api.requestOtp(phone);
      setDevOtp(r.dev_otp);          // dev convenience; in prod arrives via SMS
      if (r.dev_otp) setOtp(r.dev_otp);
      setStep(1);
    } catch (e) { setErr(e.message); }
  }

  async function finish() {
    setErr("");
    try {
      const r = await api.onboard({
        phone, code: otp, preferred_language: lang, district,
        gps_lat: 7.47, gps_lng: 80.62, consent,
        crops: crops.map((id) => ({ crop_id: id, season: "yala" })),
      });
      setToken(r.access_token);
      localStorage.setItem("farmingos_phone", phone);
      localStorage.setItem("farmingos_farmer_id", r.farmer_id);
      nav("/chat");
    } catch (e) { setErr(e.message); }
  }

  const cropName = (c) => ({ si: c.name_si, ta: c.name_ta, en: c.name_en }[lang] || c.name_en);

  return (
    <div className="card">
      <div className="step-dots">{[0, 1, 2].map((i) => <span key={i} className={i <= step ? "on" : ""} />)}</div>
      <h2>{t("onboardWelcome")}</h2>

      {step === 0 && (
        <>
          <label>{t("phone")}</label>
          <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+9477..." />
          <button className="btn" onClick={sendOtp} disabled={!phone}>{t("sendOtp")}</button>
        </>
      )}

      {step === 1 && (
        <>
          <label>{t("otp")}</label>
          <input value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="123456" />
          {devOtp && <p className="muted">dev code: {devOtp}</p>}
          <label>{t("district")}</label>
          <select value={district} onChange={(e) => setDistrict(e.target.value)}>
            {DISTRICTS.map((d) => <option key={d}>{d}</option>)}
          </select>
          <button className="btn" onClick={() => setStep(2)} disabled={!otp}>{t("next")}</button>
        </>
      )}

      {step === 2 && (
        <>
          <label>{t("crop")}</label>
          <select multiple value={crops} onChange={(e) =>
            setCrops(Array.from(e.target.selectedOptions).map((o) => o.value))} style={{ height: 130 }}>
            {allCrops.map((c) => <option key={c.id} value={c.id}>{cropName(c)}</option>)}
          </select>
          <label style={{ display: "flex", gap: ".5rem", alignItems: "flex-start", marginTop: ".8rem" }}>
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
                   style={{ width: "auto", marginTop: ".2rem" }} />
            <span>{t("consent")}</span>
          </label>
          <button className="btn" onClick={finish} disabled={!consent}>{t("finish")}</button>
        </>
      )}

      {err && <div className="error">{err}</div>}
    </div>
  );
}
