import type { AppState } from "../types";
import { estimateEpisode } from "../utils";
import { useI18n } from "../i18n/I18nProvider";

// Visual style for a scene's generated animation — same set the character
// builder offers (CastStep STYLE_OPTIONS).
const SCENE_STYLE_OPTIONS = [
  "realistic",
  "lego",
  "muppet",
  "pixar",
  "ghibli",
  "comic",
  "anime",
  "south_park",
];

// Background presets — mirror the character STYLE_OPTIONS pattern in CastStep.
// "custom" reveals a free-text input so the user can describe any scene.
const BACKGROUND_OPTIONS = [
  "none",
  "news studio",
  "moving car",
  "office",
  "city street",
  "kitchen",
  "living room",
  "park / outdoor",
  "classroom",
  "custom",
];

type ScriptStepProps = {
  state: AppState;
  onSetTitle: (title: string) => void;
  onAddSegment: (character: string) => void;
  onAddScene: (character: string) => void;
  onUpdateSegment: (index: number, updates: Partial<AppState["segments"][number]>) => void;
  onMoveSegment: (index: number, delta: number) => void;
  onRemoveSegment: (index: number) => void;
  onBack: () => void;
  onContinue: () => void;
};

export function ScriptStep({
  state,
  onSetTitle,
  onAddSegment,
  onAddScene,
  onUpdateSegment,
  onMoveSegment,
  onRemoveSegment,
  onBack,
  onContinue,
}: ScriptStepProps) {
  const { t } = useI18n();
  const segments = state.segments;
  const cast = state.cast;
  const summary = estimateEpisode(segments);
  // A scene is valid once it has an animation prompt (narration is optional);
  // a dialogue segment needs its spoken line.
  const canContinue =
    segments.length > 0 &&
    segments.every((segment) =>
      segment.kind === "scene"
        ? (segment.animationPrompt ?? "").trim().length > 0
        : segment.text.trim().length > 0,
    );

  return (
    <div>
      <div className="page-title-row">
        <div>
          <h2>{t("writeTheScript")}</h2>
          <p className="muted">{t("eachSegmentDescription")}</p>
        </div>
      </div>

      <label className="full-width">
        {t("episodeTitle")}
        <input
          value={state.title}
          onChange={(event) => onSetTitle(event.target.value)}
          placeholder={t("episodeTitlePlaceholder")}
        />
      </label>

      <div className="script-layout">
        <div className="script-main-container">
          <div className="script-main">
            {segments.length === 0 ? (
              <div className="card empty-card">
                <p>{t("noSegmentsYet")}</p>
              </div>
            ) : null}

            {segments.map((segment, index) => {
              const isScene = segment.kind === "scene";
              const moveControls = (
                <div className="segment-actions">
                  <button type="button" onClick={() => onMoveSegment(index, -1)} disabled={index === 0}>
                    ↑
                  </button>
                  <button type="button" onClick={() => onMoveSegment(index, 1)} disabled={index === segments.length - 1}>
                    ↓
                  </button>
                  <button type="button" className="destructive" onClick={() => onRemoveSegment(index)}>
                    ✕
                  </button>
                </div>
              );
              const narratorSelect = (
                <select
                  title={isScene ? t("narratorTitle") : t("characterTitle")}
                  value={segment.character}
                  onChange={(event) => onUpdateSegment(index, { character: event.target.value })}
                >
                  {cast.map((character) => (
                    <option key={character.slug} value={character.slug}>
                      {character.displayName}
                    </option>
                  ))}
                </select>
              );

              if (isScene) {
                return (
                  <div key={index} className="segment-card scene-card">
                    <div className="segment-header">
                      <div className="segment-selects">
                        <span className="scene-badge">🎬 {t("sceneLabel")}</span>
                        <select
                          title="Visual style"
                          value={segment.style ?? "realistic"}
                          onChange={(event) => onUpdateSegment(index, { style: event.target.value })}
                        >
                          {SCENE_STYLE_OPTIONS.map((style) => (
                            <option key={style} value={style}>
                              {style}
                            </option>
                          ))}
                        </select>
                      </div>
                      {moveControls}
                    </div>
                    <input
                      className="scene-prompt"
                      value={segment.animationPrompt ?? ""}
                      onChange={(event) => onUpdateSegment(index, { animationPrompt: event.target.value })}
                      placeholder={t("animationPromptPlaceholder")}
                    />
                    <textarea
                      className="script-textarea"
                      dir="rtl"
                      value={segment.text}
                      onChange={(event) => onUpdateSegment(index, { text: event.target.value })}
                      placeholder={t("sceneNarrationPlaceholder")}
                    />
                    <div className="segment-footer">
                      <span>{t("sceneNarrationOptional")}</span>
                      <span>{segment.text.length} chars</span>
                    </div>
                  </div>
                );
              }

              const bg = segment.background ?? "";
              // The select shows "custom" whenever the stored value isn't one of
              // the presets (and isn't empty) — that's a free-text scene.
              const isPresetBg = bg === "" || BACKGROUND_OPTIONS.includes(bg);
              const bgSelectValue = bg === "" ? "none" : isPresetBg ? bg : "custom";
              return (
              <div key={index} className="segment-card">
                <div className="segment-header">
                  <div className="segment-selects">
                    {narratorSelect}
                    <select
                      title={t("backgroundTitle")}
                      value={bgSelectValue}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (value === "none") onUpdateSegment(index, { background: "" });
                        else if (value === "custom") onUpdateSegment(index, { background: " " });
                        else onUpdateSegment(index, { background: value });
                      }}
                    >
                      {BACKGROUND_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {t(`background_${option.replace(/[^a-z]+/gi, "_")}`)}
                        </option>
                      ))}
                    </select>
                    {bgSelectValue === "custom" && (
                      <input
                        className="segment-bg-custom"
                        value={bg.trim() === "" ? "" : bg}
                        onChange={(event) => onUpdateSegment(index, { background: event.target.value })}
                        placeholder={t("backgroundCustomPlaceholder")}
                      />
                    )}
                  </div>
                  {moveControls}
                </div>
                <textarea
                  className="script-textarea"
                  dir="rtl"
                  value={segment.text}
                  onChange={(event) => onUpdateSegment(index, { text: event.target.value })}
                  placeholder={t("hebrewPlaceholder")}
                />
                <div className="segment-footer">
                  <span>{Math.max(1, segment.text.trim().length / 15).toFixed(1)}s audio</span>
                  <span>{segment.text.length} chars</span>
                </div>
              </div>
              );
            })}

            <div className="segment-add-row">
              <button type="button" className="secondary" onClick={() => onAddSegment(cast[0]?.slug || "")}>{t("addSegment")}</button>
              <button type="button" className="secondary" onClick={() => onAddScene(cast[0]?.slug || "")}>{t("addScene")}</button>
            </div>
          </div>
        </div>
        <aside className="script-summary">
          <div className="card summary-card">
            <p className="tiny">{t("estimate")}</p>
            <h2>{summary.audio_secs.toFixed(0)}s</h2>
            <p className="muted">{t("totalAudio")}</p>
            <h2>${summary.cost_usd.toFixed(2)}</h2>
            <p className="muted">{t("renderCost")}</p>
            <hr />
            <p className="tiny">
              {summary.segments} {t("segments")}{summary.segments !== 1 ? "s" : ""}
            </p>
          </div>
        </aside>
      </div>

      <div className="footer-row">
        <button type="button" onClick={onContinue} className="primary" disabled={!canContinue}>
          {t("continueToVoice")}
        </button>
        <button type="button" onClick={onBack} className="secondary">
          {t("back")}
        </button>
      </div>
    </div>
  );
}
