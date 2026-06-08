import { useMemo, useRef, useState } from "react";
import type { AppState, Candidate, Character } from "../types";
import { getCandidateImageUrl, safeSlug } from "../utils";
import { useI18n } from "../i18n/I18nProvider";
import { API, API_BASE } from "../api";
import { VoiceSelect } from "./VoiceSelect";

const STYLE_OPTIONS = [
  "realistic",
  "lego",
  "muppet",
  "pixar",
  "ghibli",
  "comic",
  "anime",
  "south_park",
];

const TEMPO_OPTIONS = [
  { label: "Calm", value: 1.0 },
  { label: "Natural", value: 1.0 },
  { label: "Urgent", value: 1.25 },
];

type CastStepProps = {
  state: AppState;
  onAddCharacter: (character: Character) => void;
  onRemoveCharacter: (slug: string) => void;
  onLoadDemo: () => void;
  onContinue: () => void;
};

const defaultDraft = {
  slug: "",
  displayName: "",
  description: "",
  style: "lego",
  voiceId: "",
  voiceName: "",
  tempo: 1.0,
  public: true,
  compareStyles: false,
  count: 3,
};

// Generated candidates use idx >= 1; the uploaded image gets this reserved idx
// so it can sit in the same selectable grid.
const UPLOAD_IDX = 0;

export function CastStep({ state, onAddCharacter, onRemoveCharacter, onLoadDemo, onContinue }: CastStepProps) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ ...defaultDraft });
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [generateCount, setGenerateCount] = useState(3);
  // Uploaded image (data URL). When set, the character is saved from this
  // image instead of from a generated candidate.
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const cast = state.cast;
  const canContinue = cast.length >= 1 && cast.length <= 4;

  // The uploaded image (if any) shown as a candidate, prepended to the
  // generated ones so it's selectable in the same grid.
  const allCandidates = useMemo<Candidate[]>(() => {
    const uploaded: Candidate[] = uploadedImage
      ? [{ idx: UPLOAD_IDX, style: draft.style, imageUrl: uploadedImage }]
      : [];
    return [...uploaded, ...candidates];
  }, [uploadedImage, candidates, draft.style]);

  const selectedImage = useMemo(() => {
    if (selected === null) return undefined;
    return allCandidates.find((candidate) => candidate.idx === selected)?.imageUrl;
  }, [allCandidates, selected]);

  const startEditing = (character?: Character) => {
    setDraft(
      character
        ? {
          slug: character.slug,
          displayName: character.displayName,
          description: character.description,
          style: character.style,
          voiceId: character.voiceId,
          voiceName: character.voiceName,
          tempo: character.tempo,
          public: character.public ?? true,
          compareStyles: false,
          count: 3,
        }
        : { ...defaultDraft },
    );
    setCandidates([]);
    setSelected(null);
    setUploadedImage(null);
    setEditing(true);
  };

  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setUploadedImage(typeof reader.result === "string" ? reader.result : null);
      setSelected(UPLOAD_IDX); // auto-select the upload (still re-selectable)
    };
    reader.readAsDataURL(file);
    event.target.value = ""; // allow re-selecting the same file
  };

  const removeUploadedImage = () => {
    setUploadedImage(null);
    setSelected((s) => (s === UPLOAD_IDX ? null : s));
  };

  const startNewCharacter = () => startEditing();
  const startEditCharacter = (character: Character) => () => startEditing(character);

  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const saveCharacter = async () => {
    const slug = safeSlug(draft.slug || draft.displayName || "character");
    const displayName = draft.displayName || slug.replace(/_/g, " ");
    const voice = { voice_id: draft.voiceId, voice_name: draft.voiceName, tempo: draft.tempo };
    setSaveError(null);
    setSaving(true);
    try {
      let imageUrl: string;
      if (selected === UPLOAD_IDX && uploadedImage) {
        // Save directly from the uploaded image (POST /characters).
        const resp = await fetch(API.characters.create, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            slug,
            display_name: displayName,
            description: draft.description,
            style: draft.style,
            public: draft.public,
            image_base64: uploadedImage,
            voice,
          }),
        });
        if (!resp.ok) {
          const detail = await resp.text();
          throw new Error(`save failed (${resp.status}): ${detail}`);
        }
        const data = await resp.json();
        imageUrl = data.character?.image_url ? `${API_BASE}${data.character.image_url}` : uploadedImage;
      } else {
        // Promote a generated candidate (POST /characters/promote).
        const idx = selected ?? 1;
        const resp = await fetch(API.characters.promote, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            slug,
            idx,
            display_name: displayName,
            description: draft.description,
            style: draft.style,
            public: draft.public,
            voice,
          }),
        });
        if (!resp.ok) {
          const detail = await resp.text();
          throw new Error(`promote failed (${resp.status}): ${detail}`);
        }
        const data = await resp.json();
        imageUrl = data.character?.image_url
          ? `${API_BASE}${data.character.image_url}`
          : selectedImage || getCandidateImageUrl(slug, idx);
      }
      onAddCharacter({
        slug,
        displayName,
        description: draft.description,
        style: draft.style,
        voiceId: draft.voiceId,
        voiceName: draft.voiceName,
        tempo: draft.tempo,
        public: draft.public,
        imageUrl,
      });
      setEditing(false);
      setUploadedImage(null);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };
  const generateCandidates = () => {
    const slug = safeSlug(draft.slug || draft.displayName || "character");
    // Call backend to generate candidates
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/characters/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slug, description: draft.description, style: draft.style, count: generateCount }),
        });
        if (!resp.ok) throw new Error(`server error: ${resp.status}`);
        const data = await resp.json();
        const list = (data.candidates || []).map((c: any) => ({ idx: c.idx, style: draft.style, imageUrl: `${API_BASE}${c.image_url}` }));
        if (list.length === 0) {
          // Fallback to placeholders
          setCandidates(
            Array.from({ length: generateCount }, (_, index) => ({
              idx: index + 1,
              style: draft.style,
              imageUrl: getCandidateImageUrl(slug, index + 1),
            })),
          );
          setSelected(1);
        } else {
          setCandidates(list);
          setSelected(list[0]?.idx ?? 1);
        }
      } catch (err) {
        // On error, show placeholders so the UI remains responsive
        setCandidates(
          Array.from({ length: generateCount }, (_, index) => ({
            idx: index + 1,
            style: draft.style,
            imageUrl: getCandidateImageUrl(slug, index + 1),
          })),
        );
        setSelected(1);
      }
    })();
  };

  return (
    <div>
      <div className="page-title-row">
        <div>
          <h2>{t("buildYourCast")}</h2>
          <p className="muted">{t("buildYourCastDescription")}</p>
        </div>
      </div>

      {cast.length === 0 && !editing ? (
        <div className="empty-state-grid">
          <button type="button" className="card large" onClick={startNewCharacter}>
            <h3>{t("buildYourOwn")}</h3>
            <p>{t("buildYourOwnDescription")}</p>
          </button>
          <button type="button" className="card large" onClick={onLoadDemo}>
            <h3>{t("tryDemo")}</h3>
            <p>{t("tryDemoDescription")}</p>
          </button>
        </div>
      ) : null}
      
      {cast.length > 0 && !editing ? (
        <div className="cards-grid">
          {cast.map((character) => (
            <div key={character.slug} className="card character-card">
              <img src={character.imageUrl} alt={character.displayName} />
              <div className="card-meta">
                <strong>{character.displayName}</strong>
                <p className="tiny">@{character.slug} · {character.voiceName || "—"}</p>
              </div>
              <div className="card-actions">
                <button type="button" onClick={startEditCharacter(character)}>
                  {t("edit")}
                </button>
                <button type="button" className="destructive" onClick={() => onRemoveCharacter(character.slug)}>
                  {t("remove")}
                </button>
              </div>
            </div>
          ))}
          {cast.length < 4 && (
            <button type="button" className="card add-tile" onClick={startNewCharacter}>
              <div>+</div>
              <p>{t("addCharacterCard")}</p>
            </button>
          )}
        </div>
      ) : null}

      {editing ? (
        <div className="wizard-card">
          <h3>{cast.length ? t("addOrEditCharacter") : t("createYourFirstCharacter")}</h3>
          <div className="form-grid">
            <label>
              <span>
                {t("description")}
                {uploadedImage ? <span className="muted"> — optional (using your uploaded image)</span> : null}
              </span>
              <div className="characterDescriptionInfo">
                <textarea
                  value={draft.description}
                  onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                  placeholder={uploadedImage ? "Optional — you've uploaded an image" : t("descriptionPlaceholder")}
                />
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <button type="button" className="secondary" onClick={() => fileInputRef.current?.click()}>
                    📁 {uploadedImage ? "Change image" : "Upload image"}
                  </button>
                  {uploadedImage && (
                    <>
                      <img
                        src={uploadedImage}
                        alt="uploaded preview"
                        style={{ width: 40, height: 40, objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)" }}
                      />
                      <button type="button" className="secondary" onClick={removeUploadedImage}>
                        Remove
                      </button>
                    </>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={handleImageUpload}
                    style={{ display: "none" }}
                  />
                </div>
              </div>
            </label>
            <label style={uploadedImage ? { opacity: 0.5 } : undefined}>
              <span>
                {t("style")}
                {uploadedImage ? <span className="muted"> — not used with an uploaded image</span> : null}
              </span>
              <select
                value={draft.style}
                disabled={!!uploadedImage}
                onChange={(event) => setDraft({ ...draft, style: event.target.value })}
              >
                {STYLE_OPTIONS.map((style) => (
                  <option key={style} value={style}>{style}</option>
                ))}
              </select>
            </label>
            <label>
              {t("voiceId")}
              <VoiceSelect
                voiceId={draft.voiceId}
                voiceName={draft.voiceName}
                onChange={(id, name) => setDraft({ ...draft, voiceId: id, voiceName: name || draft.voiceName })}
                placeholder={t("voiceIdPlaceholder")}
              />
            </label>
            <label>
              {t("voiceName")}
              <input
                value={draft.voiceName}
                onChange={(event) => setDraft({ ...draft, voiceName: event.target.value })}
                placeholder={t("voiceNamePlaceholder")}
              />
            </label>
            <label>
              {t("displayName")}
              <input
                value={draft.displayName}
                onChange={(event) => setDraft({ ...draft, displayName: event.target.value })}
                placeholder={t("displayNamePlaceholder")}
              />
            </label>
            <label>
              {t("slug")}
              <input
                value={draft.slug}
                onChange={(event) => setDraft({ ...draft, slug: event.target.value })}
                placeholder={t("slugPlaceholder")}
              />
            </label>
            <label>
              {t("tempo")}
              <select value={draft.tempo} onChange={(event) => setDraft({ ...draft, tempo: Number(event.target.value) })}>
                {TEMPO_OPTIONS.map((option) => (
                  <option key={option.label} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              {t("candidateCount")}
              <input
                type="number"
                min={1}
                max={5}
                value={generateCount}
                onChange={(event) => setGenerateCount(Number(event.target.value))}
              />
            </label>
          </div>
 <div className="cast-container">
           
            <button type="button" onClick={generateCandidates}>{t("generateCandidates")}</button>
            <button type="button" className="secondary" onClick={() => { setEditing(false); setUploadedImage(null); }}>
              {t("cancel")}
            </button>
           
         
            {allCandidates.length > 0 && (
              <>
                <h4>{t("pickOneCandidate")}</h4>
                <div className="cards-grid">
                  {allCandidates.map((candidate) => {
                    const isUpload = candidate.idx === UPLOAD_IDX;
                    const caption = isUpload ? "📁 Your upload" : `${t("optionLabel")} ${candidate.idx}`;
                    return (
                      <button
                        type="button"
                        key={candidate.idx}
                        className={`candidate-card ${selected === candidate.idx ? "selected" : ""}`}
                        onClick={() => setSelected(candidate.idx)}
                      >
                        <img src={candidate.imageUrl} alt={caption} />
                        <div className="candidate-caption">{caption}</div>
                      </button>
                    );
                  })}
                </div>

                {selected !== null && (
                  <div className="public-toggle-container" style={{  padding: "12px 16px", backgroundColor: "#f8f9fa", borderRadius: "6px", border: "1px solid #e9ecef" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer", margin: 0 }}>
                      <input
                        type="checkbox"
                        checked={draft.public}
                        onChange={(e) => setDraft({ ...draft, public: e.target.checked })}
                        style={{ cursor: "pointer" }}
                      />
                      <div>
                        <div><strong>{draft.public ? "🌍 Public Character" : "🔒 Private Character"}</strong></div>
                        <div style={{ fontSize: "0.85em", color: "#666", marginTop: "4px" }}>
                          {draft.public ? "This character will appear in the shared library for all users" : "Only you can use this character"}
                        </div>
                      </div>
                    </label>
                  </div>
                )}

              <div className="wizard-actions">
                <button type="button" disabled={selected === null || saving} onClick={saveCharacter}>
                  {saving ? "…" : t("saveCharacter")}
                </button>
              </div>
              {saveError ? <p className="error">{saveError}</p> : null}
            </>
          )}
          </div>
        </div>
      ) : null}

      <div className="footer-row">
        <button type="button" onClick={onContinue} className="primary" disabled={!canContinue}>
          {t("continueToStep2")}
        </button>
      </div>
      <div className="space-holder" />
    </div>
  );
}
