import { useEffect, useState } from "react";
import type { Character, LibraryVideo } from "../types";
import { useI18n } from "../i18n/I18nProvider";
import { API, API_BASE } from "../api";

type CharacterLibraryProps = {
  cast: Character[];
  onAddCharacter: (character: Character) => void;
};

type LibraryTab = "characters" | "videos";

type ApiCharacter = {
  slug: string;
  display_name: string;
  description: string;
  style: string;
  image_url: string;
  public?: boolean;
  voice: { voice_id: string; voice_name?: string; tempo?: number };
};

type ApiVideo = {
  slug: string;
  title: string;
  video_url: string;
  created_at: number;
};

function toVideo(v: ApiVideo): LibraryVideo {
  return {
    slug: v.slug,
    title: v.title,
    videoUrl: `${API_BASE}${v.video_url}`,
    createdAt: v.created_at,
  };
}

function toCharacter(c: ApiCharacter): Character {
  return {
    slug: c.slug,
    displayName: c.display_name,
    description: c.description,
    style: c.style,
    voiceId: c.voice?.voice_id ?? "",
    voiceName: c.voice?.voice_name ?? "",
    tempo: c.voice?.tempo ?? 1.0,
    imageUrl: `${API_BASE}${c.image_url}`,
    public: c.public,
  };
}

export function CharacterLibrary({ cast, onAddCharacter }: CharacterLibraryProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<LibraryTab>("characters");
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [videos, setVideos] = useState<LibraryVideo[]>([]);
  const [videosLoading, setVideosLoading] = useState(false);
  const [videosError, setVideosError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch once, the first time the drawer is opened. `open` is the only
    // dependency on purpose: including `loading`/`characters.length` makes the
    // effect re-run as soon as we call setLoading, which fires this run's
    // cleanup and cancels the in-flight fetch before it can store results.
    if (!open || characters.length > 0) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const resp = await fetch(API.characters.list);
        if (!resp.ok) throw new Error(`server error: ${resp.status}`);
        const data = await resp.json();
        if (cancelled) return;
        setCharacters((data.characters || []).map(toCharacter));
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Fetch the rendered-video list whenever the Videos tab is shown while the
  // drawer is open. Re-fetch each time the tab is entered so freshly rendered
  // videos appear without a reload.
  useEffect(() => {
    if (!open || tab !== "videos") return;
    let cancelled = false;
    setVideosLoading(true);
    setVideosError(null);
    (async () => {
      try {
        const resp = await fetch(API.video.list);
        if (!resp.ok) throw new Error(`server error: ${resp.status}`);
        const data = await resp.json();
        if (cancelled) return;
        setVideos((data.videos || []).map(toVideo));
      } catch (err) {
        if (!cancelled) setVideosError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setVideosLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, tab]);

  const castFull = cast.length >= 4;

  return (
    <>
      <button
        type="button"
        className="library-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("characterLibrary")}
      >
        {open ? "›" : "‹"} {t("library")}
      </button>

      {open && <div className="library-backdrop" onClick={() => setOpen(false)} />}

      <aside className={`library-drawer ${open ? "open" : ""}`} aria-hidden={!open}>
        <div className="library-header">
          <h2>{tab === "characters" ? t("characterLibrary") : t("videoLibrary")}</h2>
          <button
            type="button"
            className="icon-button"
            onClick={() => setOpen(false)}
            aria-label={t("close")}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="library-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "characters"}
            className={`library-tab ${tab === "characters" ? "active" : ""}`}
            onClick={() => setTab("characters")}
          >
            {t("charactersTab")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "videos"}
            className={`library-tab ${tab === "videos" ? "active" : ""}`}
            onClick={() => setTab("videos")}
          >
            {t("videosTab")}
          </button>
        </div>

        {tab === "characters" ? (
          <>
            <p className="muted">{t("characterLibraryDescription")}</p>

            {loading && <p className="muted">{t("loading")}</p>}
            {error && <div className="warning-card">{error}</div>}
            {!loading && !error && characters.length === 0 && (
              <p className="muted">{t("libraryEmpty")}</p>
            )}

            <div className="library-list">
              {characters.map((character) => {
                const inCast = cast.some((c) => c.slug === character.slug);
                return (
                  <div key={character.slug} className="library-item">
                    <img
                      src={character.imageUrl}
                      alt={character.displayName}
                      onError={(e) => {
                        const img = e.currentTarget;
                        if (img.dataset.fallback) return;
                        img.dataset.fallback = "1";
                        img.classList.add("library-item-img-fallback");
                        img.removeAttribute("src");
                      }}
                    />
                    <div className="library-item-meta">
                      <strong>{character.displayName}</strong>
                      <p className="tiny">@{character.slug} · {character.style}</p>
                    </div>
                    <button
                      type="button"
                      className="secondary"
                      disabled={inCast || castFull}
                      onClick={() => onAddCharacter(character)}
                    >
                      {inCast ? t("inCast") : t("addToCast")}
                    </button>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <>
            <p className="muted">{t("videoLibraryDescription")}</p>

            {videosLoading && <p className="muted">{t("loading")}</p>}
            {videosError && <div className="warning-card">{videosError}</div>}
            {!videosLoading && !videosError && videos.length === 0 && (
              <p className="muted">{t("videosEmpty")}</p>
            )}

            <div className="library-list">
              {videos.map((video) => (
                <div key={video.slug} className="library-video-item">
                  <video className="library-video" src={video.videoUrl} controls preload="metadata" />
                  <div className="library-item-meta">
                    <strong>{video.title}</strong>
                    <p className="tiny">@{video.slug}</p>
                  </div>
                  <a
                    className="secondary library-video-open"
                    href={video.videoUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t("openVideo")}
                  </a>
                </div>
              ))}
            </div>
          </>
        )}
      </aside>
    </>
  );
}
