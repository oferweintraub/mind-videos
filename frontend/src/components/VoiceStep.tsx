import { ChangeEvent, useState } from "react";
import type { AppState, VoiceSample } from "../types";
import { useI18n } from "../i18n/I18nProvider";

type VoiceStepProps = {
  state: AppState;
  onSetVoiceSample: (slug: string, sample: VoiceSample | null) => void;
  onBack: () => void;
  onContinue: () => void;
};

const ACCEPTED_MIME = "audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/webm,audio/mp4,audio/m4a,audio/x-m4a";
const MAX_BYTES = 10 * 1024 * 1024; // 10 MB cap, ElevenLabs IVC accepts up to ~25 MB but keep payloads small

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error || new Error("read failed"));
    reader.readAsDataURL(file);
  });
}

export function VoiceStep({ state, onSetVoiceSample, onBack, onContinue }: VoiceStepProps) {
  const { t } = useI18n();
  const [uploadingFor, setUploadingFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePick = async (slug: string, event: ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError(t("voiceFileTooLarge"));
      return;
    }
    setUploadingFor(slug);
    try {
      const dataUrl = await readAsDataUrl(file);
      onSetVoiceSample(slug, {
        fileName: file.name,
        mimeType: file.type || "audio/mpeg",
        dataUrl,
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setUploadingFor(null);
    }
  };

  const count = Object.keys(state.voiceSamples).length;

  return (
    <div>
      <div className="page-title-row">
        <div>
          <h2>{t("voiceCloning")}</h2>
          <p className="muted">{t("voiceCloningDescription")}</p>
        </div>
      </div>

      {error && <div className="warning-card">{error}</div>}

      {state.cast.length === 0 ? (
        <div className="card empty-card">
          <p>{t("noCastForVoice")}</p>
        </div>
      ) : (
        <div className="voice-list">
          {state.cast.map((character) => {
            const sample = state.voiceSamples[character.slug];
            const isUploading = uploadingFor === character.slug;
            return (
              <div key={character.slug} className="card voice-row">
                <div className="voice-row-head">
                  <img src={character.imageUrl} alt={character.displayName} className="voice-avatar" />
                  <div className="voice-row-meta">
                    <strong>{character.displayName}</strong>
                    <p className="tiny muted">{t("currentVoice")}: {character.voiceName || character.voiceId || "—"}</p>
                  </div>
                </div>

                {sample ? (
                  <div className="voice-sample">
                    <audio controls src={sample.dataUrl} />
                    <div className="voice-sample-meta">
                      <span className="tiny">{sample.fileName}</span>
                      <button
                        type="button"
                        className="destructive"
                        onClick={() => onSetVoiceSample(character.slug, null)}
                      >
                        {t("removeVoiceSample")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <label className={`voice-upload ${isUploading ? "uploading" : ""}`}>
                    <input
                      type="file"
                      accept={ACCEPTED_MIME}
                      onChange={(event) => handlePick(character.slug, event)}
                      disabled={isUploading}
                    />
                    <span>{isUploading ? t("voiceLoading") : t("uploadVoiceSample")}</span>
                  </label>
                )}
              </div>
            );
          })}
        </div>
      )}

      <p className="muted tiny voice-hint">{t("voiceHint")}</p>

      <div className="footer-row">
        <button type="button" className="secondary" onClick={onBack}>
          {t("back")}
        </button>
        <button type="button" className="primary" onClick={onContinue}>
          {count > 0
            ? t("continueToRenderWithVoice", { count: String(count) })
            : t("skipVoiceContinue")}
        </button>
      </div>
    </div>
  );
}
