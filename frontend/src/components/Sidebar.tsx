import { useState, type ChangeEvent } from "react";
import type { APIKeys, AppState, AuthUser } from "../types";
import { useI18n } from "../i18n/I18nProvider";
import type { Lang } from "../i18n/dictionary";

type SidebarProps = {
  apiKeys: APIKeys;
  authUser: AuthUser | null;
  onLogout: () => void;
  shareKeys: boolean;
  onToggleShareKeys: (value: boolean) => void;
  recentProjects: AppState["recentProjects"];
  projectId: string | null;
  onUpdateKey: (key: keyof APIKeys, value: string) => void;
  onApply: () => Promise<boolean>;
  onReset: () => void;
  onExport: () => void;
  onImport: (project: AppState) => void;
  onLoadDemo: () => void;
  onClose?: () => void;
};

const LANGUAGE_NAMES: Record<Lang, string> = {
  en: "English",
  he: "עברית",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
  el: "Ελληνικά",
};

export function Sidebar({
  apiKeys,
  shareKeys,
  recentProjects,
  projectId,
  onUpdateKey,
  onApply,
  onToggleShareKeys,
  onReset,
  onExport,
  onImport,
  onLoadDemo,
  authUser,
  onLogout,
  onClose,
}: SidebarProps) {
  const { t, lang, setLang } = useI18n();
  const [applyState, setApplyState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  const handleApply = async () => {
    setApplyState("saving");
    const ok = await onApply();
    setApplyState(ok ? "saved" : "error");
    window.setTimeout(() => setApplyState("idle"), 2200);
  };

  const handleImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const project = JSON.parse(text) as AppState;
      onImport(project);
    } catch (error) {
      alert(t("invalidProjectFile"));
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-card">
        <div className="sidebar-card-header">
          <h2>{t("settings")}</h2>
          {onClose ? (
            <button type="button" className="icon-button sidebar-close" onClick={onClose} aria-label={t("closeSettings")}>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          ) : null}
        </div>
        <p className="muted">{t("apiKeysDescription")}</p>
        <div className="field-group">
          <label>{t("falAiLabel")}</label>
          <input
            type="password"
            title={t("falAiTitle")}
            value={apiKeys.fal}
            onChange={(event) => onUpdateKey("fal", event.target.value)}
          />
        </div>
        <div className="field-group">
          <label>{t("elevenLabsLabel")}</label>
          <input
            type="password"
            title={t("elevenLabsTitle")}
            value={apiKeys.elevenlabs}
            onChange={(event) => onUpdateKey("elevenlabs", event.target.value)}
          />
        </div>
        <div className="field-group">
          <label>{t("googleAiLabel")}</label>
          <input
            type="password"
            title={t("googleAiTitle")}
            value={apiKeys.google}
            onChange={(event) => onUpdateKey("google", event.target.value)}
          />
        </div>
        <div className="field-group checkbox-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={shareKeys}
              onChange={(event) => onToggleShareKeys(event.target.checked)}
            />
            {t("shareKeysWithTools")}
          </label>
        </div>
        <div className="field-group">
          <label>{t("language")}</label>
          <select value={lang} onChange={(event) => setLang(event.target.value as Lang)} title={t("languageTitle")}>
            {Object.entries(LANGUAGE_NAMES).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="settings-apply">
          <button
            type="button"
            className="primary"
            onClick={handleApply}
            disabled={applyState === "saving"}
          >
            {applyState === "saving" ? t("applying") : t("applySettings")}
          </button>
          {applyState === "saved" && (
            <span className="settings-apply-msg ok">{t("settingsSaved")}</span>
          )}
          {applyState === "error" && (
            <span className="settings-apply-msg err">{t("settingsSaveFailed")}</span>
          )}
        </div>
      </div>
      <div className="sidebar-card">
        <h2>{t("projectSection")}</h2>
        <button type="button" onClick={onExport} className="secondary">
          {t("exportProjectJson")}
        </button>
        <label className="file-upload">
          {t("importProjectJson")}
          <input type="file" accept=".json" onChange={handleImport} />
        </label>
        <button type="button" onClick={onReset} className="secondary">
          {t("startNewProjectButton")}
        </button>
        <button type="button" onClick={onLoadDemo} className="secondary">
          {t("loadDemoButton")}
        </button>
      </div>
      {authUser && (
        <div className="sidebar-card">
          <h2>{t("account")}</h2>
          <p className="muted">{t("signedInAs")}</p>
          <code>{authUser.email}</code>
          <button type="button" onClick={onLogout} className="secondary" style={{ marginTop: "0.75rem" }}>
            {t("logout")}
          </button>
        </div>
      )}
      {projectId && (
        <div className="sidebar-card">
          <h2>{t("share")}</h2>
          <p className="muted">{t("copyProjectId")}</p>
          <code>{projectId}</code>
        </div>
      )}
      {recentProjects.length > 0 && (
        <div className="sidebar-card">
          <h2>{t("recent")}</h2>
          <ul className="recent-list">
            {recentProjects.slice(0, 5).map((project) => (
              <li key={project.id}>{project.title || t("untitled")}</li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
