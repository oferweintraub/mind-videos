import { useEffect, useMemo, useState } from "react";
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
  onNewProject: () => void;
};

type JobStatus = {
  id: string;
  slug: string;
  status: "queued" | "running" | "done" | "error";
  error?: string;
  final_path?: string;
};

export function RenderStep({ state, onBack, onVoiceCloned, onRenderComplete, onNewProject }: RenderStepProps) {
  const { t } = useI18n();
  const apiKeys = useSelector((s: RootState) => s.settings.apiKeys) as APIKeys;
  const [phase, setPhase] = useState<"preflight" | "running" | "done">(
    state.result ? "done" : "preflight",
  );
  const [progress, setProgress] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const downloadVideo = async () => {
    if (!videoUrl || downloading) return;
    setDownloading(true);
    try {
      const resp = await fetch(videoUrl);
      if (!resp.ok) throw new Error(`Download failed: ${resp.status}`);
      const blob = await resp.blob();
      const objectUrl = URL.createObjectURL(blob);
      const filename = `${safeSlug(state.result?.title || state.title || "video")}.mp4`;
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setRenderError(String(err));
    } finally {
      setDownloading(false);
    }
  };
  const summary = estimateEpisode(state.segments);

  // Real ElevenLabs voice IDs are 20-char base62 strings. Anything else
  // (e.g. "john", "11", "") 404s at TTS and fails the whole render.
  const VOICE_ID_RE = /^[A-Za-z0-9]{20}$/;

  // Preflight validation — a list of things to fix before spending money on a
  // render. `errors` block the Generate button; `warnings` are advisory.
  const { errors, warnings } = useMemo(() => {
    const errors: string[] = [];
    const warnings: string[] = [];
    const castBySlug = Object.fromEntries(state.cast.map((c) => [c.slug, c]));

    if (!state.title.trim()) errors.push("Give the video a name — the title is empty.");
    if (state.segments.length === 0) errors.push("Add at least one segment to the script.");
    if (!apiKeys.fal) errors.push("Add your fal.ai API key in Settings.");
    if (!apiKeys.elevenlabs) errors.push("Add your ElevenLabs API key in Settings.");

    const usedSlugs = new Set<string>();
    state.segments.forEach((seg, i) => {
      const n = i + 1;
      const isScene = seg.kind === "scene";
      if (!seg.character) {
        errors.push(`Segment ${n}: no character assigned.`);
      } else if (!castBySlug[seg.character]) {
        errors.push(`Segment ${n}: character “${seg.character}” isn’t in your cast.`);
      } else {
        usedSlugs.add(seg.character);
      }
      if (!seg.text.trim()) {
        errors.push(`Segment ${n}: ${isScene ? "scene narration" : "dialogue"} is empty.`);
      }
      if (isScene && !(seg.animationPrompt || "").trim()) {
        errors.push(`Segment ${n}: the scene needs an animation description.`);
      }
    });

    usedSlugs.forEach((slug) => {
      const c = castBySlug[slug];
      if (!c) return;
      const hasSample = !!state.voiceSamples[slug];
      if (!hasSample) {
        const vid = (c.voiceId || "").trim();
        if (!vid) {
          errors.push(`${c.displayName}: no voice selected — pick one from the voice dropdown.`);
        } else if (!VOICE_ID_RE.test(vid)) {
          errors.push(`${c.displayName}: “${vid}” isn’t a valid ElevenLabs voice id — pick a voice from the dropdown.`);
        }
      }
      if (!c.imageUrl) warnings.push(`${c.displayName}: has no image.`);
    });

    return { errors, warnings };
  }, [state, apiKeys]);

  const canRender = errors.length === 0;

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
        .map((seg) => `## ${seg.character}\n${seg.text}`)
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
          if (job.final_path) {
            const videoPath = getStaticUrl(job.final_path);
            setVideoUrl(videoPath);
            onRenderComplete(job.slug, videoPath);
          }
          setPhase("done");
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

  if (phase === "done") {
    return (
      <div>
        <h2>{t("isReady", { title: state.result?.title || state.title || t("untitled") })}</h2>
        <p className="muted">{t("watchPreview")}</p>
        <div className="video-preview">
          {videoUrl ? (
            <video
              className="videoPreview"
              key={videoUrl}
              width="100%"
              height="auto"
              controls
              autoPlay
            >
              <source src={videoUrl} type="video/mp4" />
              {t("videoNotSupported")}
            </video>
          ) : (
            <div className="video-placeholder">{t("videoLoading")}</div>
          )}
        </div>
        <div className="summary-row">
          <div className="card small-card">
            <p className="tiny">{t("renderedIn")}</p>
            <h2>{Math.floor((state.result?.elapsed ?? 0) / 60)}m {(state.result?.elapsed ?? 0) % 60}s</h2>
          </div>
          <div className="card small-card">
            <p className="tiny">{t("spent")}</p>
            <h2>${(state.result?.cost ?? 0).toFixed(2)}</h2>
          </div>
        </div>
        <div className="footer-row">
          <button type="button" className="secondary" onClick={onBack}>
            {t("editScript")}
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

      {errors.length > 0 && (
        <div className="warning-card" style={{ borderLeft: "4px solid #dc2626" }}>
          <strong>Fix {errors.length === 1 ? "this" : `these ${errors.length} things`} before generating:</strong>
          <ul style={{ margin: "8px 0 0", paddingInlineStart: 20 }}>
            {errors.map((msg, i) => (
              <li key={i} style={{ marginBottom: 4 }}>❌ {msg}</li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="info-card" style={{ marginTop: 12, padding: 14, backgroundColor: "#fffbeb", borderRadius: 10, borderLeft: "4px solid #f59e0b" }}>
          <strong>Heads up:</strong>
          <ul style={{ margin: "8px 0 0", paddingInlineStart: 20 }}>
            {warnings.map((msg, i) => (
              <li key={i} style={{ marginBottom: 4 }}>⚠️ {msg}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="footer-row">
        <button type="button" className="secondary" onClick={onBack}>
          {t("editScript")}
        </button>
        <button
          type="button"
          className="primary"
          disabled={!canRender}
          title={canRender ? undefined : "Resolve the items above first"}
          onClick={startRender}
        >
          {canRender
            ? `Generate lip-synced video · $${summary.cost_usd.toFixed(2)}`
            : `Fix ${errors.length} item${errors.length === 1 ? "" : "s"} to continue`}
        </button>
      </div>
    </div>
  );
}
