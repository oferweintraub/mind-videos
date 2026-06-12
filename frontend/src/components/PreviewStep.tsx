import { useState } from "react";
import type { AppState } from "../types";
import { safeSlug } from "../utils";
import { useI18n } from "../i18n/I18nProvider";

type PreviewStepProps = {
  state: AppState;
  onBack: () => void;
  onNewProject: () => void;
};

export function PreviewStep({ state, onBack, onNewProject }: PreviewStepProps) {
  const { t } = useI18n();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const result = state.result;
  const videoUrl = result?.videoUrl ?? null;

  const downloadVideo = async () => {
    if (!videoUrl || downloading) return;
    setDownloading(true);
    setError(null);
    try {
      const resp = await fetch(videoUrl);
      if (!resp.ok) throw new Error(`Download failed: ${resp.status}`);
      const blob = await resp.blob();
      const objectUrl = URL.createObjectURL(blob);
      const filename = `${safeSlug(result?.title || state.title || "video")}.mp4`;
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setError(String(err));
    } finally {
      setDownloading(false);
    }
  };

  if (!result) {
    return (
      <div>
        <div className="page-title-row">
          <div>
            <h2>{t("previewTitle")}</h2>
            <p className="muted">{t("previewEmpty")}</p>
          </div>
        </div>
        <div className="footer-row">
          <button type="button" className="secondary" onClick={onBack}>
            {t("back")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="video-preview-container">
      <h2>{t("isReady", { title: result.title || state.title || t("untitled") })}</h2>
      <p className="muted">{t("watchPreview")}</p>
      <div className="video-preview">
        {videoUrl ? (
          <video className="videoPreview" key={videoUrl} width="50rem" height="auto" controls autoPlay>
            <source src={videoUrl} type="video/mp4" />
            {t("videoNotSupported")}
          </video>
        ) : (
          <div className="video-placeholder">{t("videoLoading")}</div>
        )}
      </div>
      {error && <div className="warning-card">{error}</div>}
       <div >
        <div className="card small-card smallcontainer">
          <p className="tiny">{t("renderedIn")}</p>
          <h2>{Math.floor((result.elapsed ?? 0) / 60)}m {(result.elapsed ?? 0) % 60}s</h2>
        </div>
        <div className="card small-card smallcontainer">
          <p className="tiny">{t("spent")}</p>
          <h2>${(result.cost ?? 0).toFixed(2)}</h2>
        </div>
       </div>
      <div className="footer-row">
        <button type="button" className="secondary" onClick={onBack}>
          {t("back")}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={downloadVideo}
          disabled={!videoUrl || downloading}
        >
          {downloading ? t("downloading") : t("downloadVideo")}
        </button>
        <button type="button" className="primary" onClick={onNewProject}>
          {t("startNewProjectButton")}
        </button>
      </div>
    </div>
  );
}
