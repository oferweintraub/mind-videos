import { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import type { AppState, APIKeys } from "../types";
import { estimateEpisode, safeSlug } from "../utils";
import { useI18n } from "../i18n/I18nProvider";
import { API, getJobUrl, getStaticUrl } from "../api";
import { idstore } from "../redux/IDStore";

type RootState = ReturnType<typeof idstore.getState>;

type RenderStepProps = {
  state: AppState;
  onBack: () => void;
  onVoiceCloned?: (slug: string, clonedVoiceId: string) => void;
  onRenderComplete: (slug: string, videoPath: string) => void;
};

type JobStatus = {
  id: string;
  slug: string;
  status: "queued" | "running" | "done" | "error";
  error?: string;
  final_path?: string;
};

export function RenderStep({ state, onBack, onVoiceCloned, onRenderComplete }: RenderStepProps) {
  const { t } = useI18n();
  const apiKeys = useSelector((s: RootState) => s.settings.apiKeys) as APIKeys;
  const [phase, setPhase] = useState<"preflight" | "running">("preflight");
  const [progress, setProgress] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  const summary = estimateEpisode(state.segments);
  const missingKeys = [
    !apiKeys.fal && "fal.ai",
    !apiKeys.elevenlabs && "ElevenLabs",
  ].filter(Boolean);

  const startRender = async () => {
    setRenderError(null);
    setPhase("running");
    setProgress(0);
    try {
      const slug = safeSlug(state.title || "untitled");

      // Clone any uploaded voice samples first, build slug→voice_id map
      const voiceOverrides: Record<string, string> = {};
      for (const character of state.cast) {
        const sample = state.voiceSamples[character.slug];
        if (!sample) continue;
        if (sample.clonedVoiceId) {
          voiceOverrides[character.slug] = sample.clonedVoiceId;
          continue;
        }
        const cloneResp = await fetch(API.voice.clone, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: `${slug}_${character.slug}`,
            audio_base64: sample.dataUrl,
            mime_type: sample.mimeType,
            elevenlabs_api_key: apiKeys.elevenlabs,
          }),
        });
        if (!cloneResp.ok) {
          const txt = await cloneResp.text().catch(() => "");
          throw new Error(`Voice clone failed for ${character.displayName}: ${cloneResp.status} ${txt}`);
        }
        const cloneData = await cloneResp.json();
        if (!cloneData.voice_id) {
          throw new Error(`Voice clone for ${character.displayName} returned no voice_id`);
        }
        voiceOverrides[character.slug] = cloneData.voice_id;
        onVoiceCloned?.(character.slug, cloneData.voice_id);
      }

      // First: save the script
      const scriptContent = `# ${state.title || "Untitled"}\n\n${state.segments
        .map((seg) => {
          // Strip newlines/parens from heading annotations so the `## slug (key: value)`
          // line stays single-line and parseable.
          const clean = (s?: string) => (s ?? "").replace(/[\r\n)]/g, " ").trim();
          let heading = `## ${seg.character}`;
          if (seg.kind === "scene") {
            const anim = clean(seg.animationPrompt);
            if (anim) heading += ` (anim: ${anim})`;
          } else {
            const bg = clean(seg.background);
            if (bg) heading += ` (bg: ${bg})`;
          }
          return `${heading}\n${seg.text}`;
        })
        .join("\n\n")}`;
      const scriptResp = await fetch(API.script.create, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug, content: scriptContent }),
      });
      if (!scriptResp.ok) throw new Error(`Script save failed: ${scriptResp.status}`);

      // Then: kick off render
      const resp = await fetch(API.video.make, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slug,
          voice_overrides: voiceOverrides,
          api_keys: {
            fal: apiKeys.fal,
            elevenlabs: apiKeys.elevenlabs,
            google: apiKeys.google,
          },
        }),
      });
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
      const data = await resp.json();
      setJobId(data.job_id);
    } catch (err) {
      setRenderError(String(err));
      setPhase("preflight");
    }
  };

  // Poll job status when running
  useEffect(() => {
    if (phase !== "running" || !jobId) return;
    const interval = window.setInterval(async () => {
      try {
        const resp = await fetch(getJobUrl(jobId));
        if (!resp.ok) throw new Error(`Job fetch error: ${resp.status}`);
        const job: JobStatus = await resp.json();
        
        // Simulate linear progress: 30% queued, 70% running
        if (job.status === "queued") {
          setProgress(15);
        } else if (job.status === "running") {
          setProgress(Math.min(95, 40 + Math.random() * 40));
        } else if (job.status === "done") {
          setProgress(100);
          // Advance to the Preview step (5). The parent stores the video URL
          // on state.result so PreviewStep can render it.
          onRenderComplete(job.slug, job.final_path ? getStaticUrl(job.final_path) : "");
          window.clearInterval(interval);
        } else if (job.status === "error") {
          setRenderError(job.error || "Unknown error");
          setPhase("preflight");
          window.clearInterval(interval);
        }
      } catch (err) {
        setRenderError(String(err));
        setPhase("preflight");
        window.clearInterval(interval);
      }
    }, 1000);
    return () => window.clearInterval(interval);
  }, [phase, jobId, onRenderComplete]);

  if (phase === "running") {
    return (
      <div>
        <h2>
          {t("generating")} *{state.title || t("untitled")}*…
        </h2>
        <p className="muted">{t("renderPipeline")}</p>
        {renderError && <div className="warning-card">{renderError}</div>}
        <div className="progress-card">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <p>{t("progressComplete", { progress: Math.floor(progress) })}</p>
        </div>
        <div className="footer-row">
          <button type="button" className="secondary" onClick={() => setPhase("preflight")}>{t("cancelButton")}</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-title-row">
        <div>
          <h2>{t("readyToRender")}</h2>
          <p className="muted">{t("readyToRenderDescription")}</p>
        </div>
      </div>
      <div className="summary-card wide-card">
        <h3>{state.title || t("untitled")}</h3>
        <p className="muted">
          {state.cast.length} {t("characterLabel")} {state.cast.length !== 1 ? "s" : ""} · {summary.segments} {t("segmentLabel")}{summary.segments !== 1 ? "s" : ""} · {summary.audio_secs.toFixed(0)}s · <strong>${summary.cost_usd.toFixed(2)}</strong>
        </p>
      </div>
      <div className="cast-strip">
        {state.cast.map((character) => (
          <div key={character.slug} className="cast-avatar">
            <img src={character.imageUrl} alt={character.displayName} />
            <p>{character.displayName}</p>
          </div>
        ))}
      </div>
      <div className="info-card" style={{ marginTop: 16, padding: 14, backgroundColor: "#f8f9fa", borderRadius: 10 }}>
        <p style={{ margin: 0 }}>
          This will generate a <strong>lip-synced video</strong> using ElevenLabs TTS and fal.ai VEED Fabric.
        </p>
      </div>
      {renderError && <div className="warning-card">{renderError}</div>}
      {missingKeys.length > 0 ? (
        <div className="warning-card">
          {t("missingKeysPrefix")} {missingKeys.join(" and ")} {t("missingKeysSuffix")}
        </div>
      ) : null}
      <div className="footer-row">
        <button type="button" className="secondary" onClick={onBack}>
          {t("editScript")}
        </button>
        <button
          type="button"
          className="primary"
          disabled={missingKeys.length > 0 || state.segments.length === 0}
          onClick={startRender}
        >
          Generate lip-synced video · ${summary.cost_usd.toFixed(2)}
        </button>
      </div>
    </div>
  );
}
