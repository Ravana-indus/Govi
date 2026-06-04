import { useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { LangContext, STRINGS, useT } from "./i18n.js";
import Onboarding from "./pages/Onboarding.jsx";
import Chat from "./pages/Chat.jsx";
import PricePortal from "./pages/PricePortal.jsx";
import AdminConsole from "./pages/AdminConsole.jsx";
import OfficerConsole from "./pages/OfficerConsole.jsx";
import Privacy from "./pages/Privacy.jsx";

function TopBar() {
  const t = useT();
  return (
    <header className="topbar">
      <div>
        <div className="brand">🌱 {t("appName")}</div>
        <div className="tagline">{t("tagline")}</div>
      </div>
      <nav>
        <NavLink to="/" end>{t("farmer")}</NavLink>
        <NavLink to="/chat">{t("chatTitle")}</NavLink>
        <NavLink to="/privacy">{t("privacy")}</NavLink>
        <NavLink to="/price-portal">{t("pricePortal")}</NavLink>
        <NavLink to="/officer">{t("officer")}</NavLink>
        <NavLink to="/admin">{t("admin")}</NavLink>
      </nav>
      <LangSwitch />
    </header>
  );
}

function LangSwitch() {
  return (
    <LangContext.Consumer>
      {({ lang, setLang }) => (
        <div className="langs">
          {Object.keys(STRINGS).map((l) => (
            <button key={l} className={l === lang ? "active" : ""} onClick={() => setLang(l)}>
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      )}
    </LangContext.Consumer>
  );
}

export default function App() {
  const [lang, setLang] = useState(localStorage.getItem("farmingos_lang") || "si");
  const set = (l) => { setLang(l); localStorage.setItem("farmingos_lang", l); };
  return (
    <LangContext.Provider value={{ lang, setLang: set }}>
      <TopBar />
      <main className="wrap">
        <Routes>
          <Route path="/" element={<Onboarding />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/price-portal" element={<PricePortal />} />
          {/* Admin / KB console — Phase 2. Officer console — Phase 3. Both real. */}
          <Route path="/admin" element={<AdminConsole />} />
          <Route path="/officer" element={<OfficerConsole />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </LangContext.Provider>
  );
}
