import { useEffect, useMemo, useRef, useState } from "react";
import { API, API_BASE } from "../api";

type Voice = {
  id: string;
  name: string;
  tone?: string;
  good_for?: string[];
  source?: string; // "catalog" | "account"
  category?: string; // "cloned" | "premade" | "generated" | "professional"
  preview_url?: string; // playable sample (relative /static/… or absolute https)
};

type VoiceSelectProps = {
  voiceId: string;
  voiceName: string;
  onChange: (voiceId: string, voiceName: string) => void;
  placeholder?: string;
};

/**
 * Searchable voice picker. Fetches the stock catalog from GET /voices and lets
 * the user filter by name / tone / use-case. Still supports a custom voice ID
 * (e.g. a cloned voice) by typing it and choosing "Use … as voice ID".
 */
export function VoiceSelect({ voiceId, voiceName, onChange, placeholder }: VoiceSelectProps) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const stopPreview = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    setPlayingId(null);
  };

  const togglePreview = (v: Voice) => {
    if (!v.preview_url) return;
    if (playingId === v.id) {
      stopPreview();
      return;
    }
    stopPreview();
    const src = v.preview_url.startsWith("http") ? v.preview_url : `${API_BASE}${v.preview_url}`;
    const audio = new Audio(src);
    audio.onended = () => setPlayingId((cur) => (cur === v.id ? null : cur));
    audio.onerror = () => setPlayingId((cur) => (cur === v.id ? null : cur));
    audioRef.current = audio;
    setPlayingId(v.id);
    audio.play().catch(() => setPlayingId((cur) => (cur === v.id ? null : cur)));
  };

  // Stop audio when the picker unmounts.
  useEffect(() => () => stopPreview(), []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(API.voice.list);
        if (!resp.ok) return;
        const data = await resp.json();
        if (!cancelled) setVoices(Array.isArray(data.voices) ? data.voices : []);
      } catch {
        /* network error — field stays usable via custom ID */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return voices;
    return voices.filter((v) =>
      [v.name, v.tone, v.id, v.category, ...(v.good_for || [])].join(" ").toLowerCase().includes(q),
    );
  }, [voices, query]);

  const currentLabel = voiceName
    ? `${voiceName}${voiceId ? ` (${voiceId.slice(0, 8)}…)` : ""}`
    : voiceId
      ? `Custom (${voiceId.slice(0, 8)}…)`
      : "";

  const pick = (v: Voice) => {
    onChange(v.id, v.name);
    setQuery("");
    setOpen(false);
  };

  const useCustom = () => {
    const raw = query.trim();
    if (raw) onChange(raw, "");
    setQuery("");
    setOpen(false);
  };

  return (
    <div className="voice-select" ref={wrapRef} style={{ position: "relative" }}>
      <input
        type="text"
        value={open ? query : currentLabel}
        placeholder={placeholder || "Search voices by name, tone, or use…"}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
      />
      {open && (
        <div
          className="voice-options"
           
        >
          {filtered.map((v) => (
            <div
              key={v.id}
              className="voice-option"
              // Select on mousedown (with preventDefault) so it commits before
              // the input blurs — otherwise the picked label only shows after blur.
              onMouseDown={(e) => {
                e.preventDefault();
                pick(v);
              }}
            >
              <button
                type="button"
                title={v.preview_url ? (playingId === v.id ? "Stop preview" : "Play preview") : "No preview available"}
                disabled={!v.preview_url}
                onMouseDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  togglePreview(v);
                }}
                className="play-button"

              >
                {playingId === v.id ? "⏸" : "▶"}
              </button>
              <span style={{ flex: 1, minWidth: 0 }}>
                <strong>{v.name}</strong>
                {v.category === "cloned" && (
                  <span
                    style={{
                      marginLeft: 6,
                      fontSize: "0.7em",
                      fontWeight: 600,
                      color: "#7c3aed",
                      background: "#f3e8ff",
                      borderRadius: 4,
                      padding: "1px 6px",
                      verticalAlign: "middle",
                    }}
                  >
                    CLONED
                  </span>
                )}
                {v.tone ? <span style={{ color: "#666", fontSize: "0.85em" }}> — {v.tone}</span> : null}
              </span>
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: "8px 12px", color: "#666", fontSize: "0.9em" }}>
              No catalog match.
              {query.trim() && (
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    useCustom();
                  }}
                  style={{ marginLeft: 8 }}
                >
                  Use “{query.trim()}” as voice ID
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
