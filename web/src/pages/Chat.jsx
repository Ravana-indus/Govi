import { useRef, useState } from "react";
import { api } from "../api.js";
import { LangContext, useT } from "../i18n.js";
import { useContext } from "react";

export default function Chat() {
  const t = useT();
  const { lang } = useContext(LangContext);
  const [msgs, setMsgs] = useState([{ dir: "out", text: t("chatTitle") }]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();
  const phone = localStorage.getItem("farmingos_phone");
  const farmerId = localStorage.getItem("farmingos_farmer_id");

  function push(m) { setMsgs((prev) => [...prev, m]); }

  async function send() {
    if (!text.trim() || !phone) return;
    const q = text.trim();
    push({ dir: "in", text: q });
    setText(""); setBusy(true);
    try {
      const r = await api.ingest(phone, q);
      const reco = r.payload?.recommendation;
      push({ dir: "out", text: r.reply, agent: r.agent, conf: r.confidence, reco });
    } catch (e) { push({ dir: "out", text: "⚠ " + e.message }); }
    setBusy(false);
  }

  async function onFile(e) {
    const file = e.target.files[0];
    if (!file || !farmerId) return;
    push({ dir: "in", text: "📷 " + file.name });
    setBusy(true);
    try {
      const r = await api.cropDiagnose(farmerId, file, lang);
      push({ dir: "out", text: r.explanation_localized, agent: "crop",
             conf: r.confidence, reco: r.escalate ? "escalated" : r.label });
    } catch (e2) { push({ dir: "out", text: "⚠ " + e2.message }); }
    setBusy(false);
    e.target.value = "";
  }

  return (
    <div className="card">
      <h2>{t("chatTitle")}</h2>
      {!phone && <p className="muted">Complete onboarding first to start chatting.</p>}
      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.dir}`}>
            {m.text}
            {(m.agent || m.reco) && (
              <span className="meta">
                {m.agent && <span className="pill">{m.agent}</span>}{" "}
                {m.reco && <span className="pill reco">{String(m.reco).replace("go_to:", "→ ")}</span>}{" "}
                {typeof m.conf === "number" && <span className="pill">conf {Math.round(m.conf * 100)}%</span>}
              </span>
            )}
          </div>
        ))}
        {busy && <div className="msg out">…</div>}
      </div>
      <div className="composer">
        <input value={text} placeholder={t("askPlaceholder")}
               onChange={(e) => setText(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && send()} />
        <button className="btn" onClick={send} disabled={busy}>{t("send")}</button>
        <button className="btn amber" onClick={() => fileRef.current?.click()} disabled={busy}>📷</button>
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={onFile} />
      </div>
    </div>
  );
}
