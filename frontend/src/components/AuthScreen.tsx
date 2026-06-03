import { useState } from "react";
import type { AuthUser } from "../auth";
import { loginUser, registerUser } from "../auth";
import { useI18n } from "../i18n/I18nProvider";

type AuthScreenProps = {
  onLogin: (user: AuthUser, password: string) => void;
};

export function AuthScreen({ onLogin }: AuthScreenProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    if (mode === "register") {
      if (password !== confirmPassword) {
        setError(t("passwordsDoNotMatch"));
        return;
      }
      const result = await registerUser(email, password);
      if (result.success) {
        onLogin(result.user, password);
      } else {
        setError(result.message);
      }
      return;
    }

    const result = await loginUser(email, password);
    if (result.success) {
      onLogin(result.user, password);
    } else {
      setError(result.message);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <h2>{mode === "login" ? t("signIn") : t("createAccount")}</h2>
        <p className="muted">
          {mode === "login"
            ? t("loginDescription")
            : t("registerDescription")}
        </p>
        <label>
          {t("email")}
          <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" />
        </label>
        <label>
          {t("password")}
          <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" />
        </label>
        {mode === "register" && (
          <label>
            {t("confirmPassword")}
            <input
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              type="password"
            />
          </label>
        )}
        {error ? <div className="error-box">{error}</div> : null}
        <div className="auth-actions">
          <button type="button" className="primary" onClick={submit}>
            {mode === "login" ? t("signIn") : t("createAccount")}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login" ? t("createAccount") : t("haveAccountLogin")}
          </button>
        </div>
      </div>
    </div>
  );
}
