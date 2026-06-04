import { useT } from "../i18n.js";

const COPY = {
  admin: {
    title: "Admin / Knowledge-Base Console",
    blurb: "Manage validated KnowledgeDocs, crops & markets, staff & roles, feature flags, and system analytics (north-star, cost). Ships in Phase 2.",
  },
  officer: {
    title: "Extension-Officer Console",
    blurb: "The human-in-the-loop queue: claim escalations, view farmer context + the AI's draft, edit/approve, resolve, and log outcomes. Powers assisted mode. Ships in Phase 3.",
  },
};

export default function Placeholder({ role }) {
  const t = useT();
  const c = COPY[role] || COPY.admin;
  return (
    <div className="card center-min">
      <div>
        <div style={{ fontSize: "2.5rem" }}>{role === "officer" ? "🧑‍🌾" : "🛠️"}</div>
        <h2>{c.title}</h2>
        <p className="muted" style={{ maxWidth: 440, margin: "0 auto" }}>{c.blurb}</p>
        <p className="pill" style={{ marginTop: "1rem" }}>{t("comingSoon")}</p>
        <p className="muted">{t("phasedNote")} The backend endpoints already exist and are tested.</p>
      </div>
    </div>
  );
}
