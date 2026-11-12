import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { GoogleLogo } from "@phosphor-icons/react";
import { api } from "../api/client";
import { Button, ErrorText, Field } from "../components/ui";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const { t } = useTranslation();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const [email, setEmail] = useState("dev@example.com");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const dev = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.devLogin(email, "Pengembang");
      onLogin();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login">
      <div className="card">
        <div className="brand"><div className="brand-mark">L</div><div><strong>{t("app.name")}</strong><small>{t("app.tagline")}</small></div></div>
        <h1>{t("login.title")}</h1>
        <p>{t("login.body")}</p>
        {health.data?.google ? (
          <a className="button primary" href="/api/auth/login"><GoogleLogo size={18} weight="bold" />{t("login.google")}</a>
        ) : (
          <div className="note">{t("login.googleOff")}</div>
        )}
        {health.data?.dev_login && (
          <form onSubmit={(e) => { e.preventDefault(); void dev(); }} className="card soft">
            <Field label={t("login.devEmail")}><input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required /></Field>
            <Button type="submit" busy={busy}>{t("login.dev")}</Button>
          </form>
        )}
        <ErrorText error={error} />
      </div>
    </div>
  );
}
