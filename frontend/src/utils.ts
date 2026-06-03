import type { Segment } from "./types";

export const CHARS_PER_SEC = 15;
export const LIPSYNC_USD_PER_SEC = 0.08;
export const TTS_USD_PER_SEG = 0.05;
// Flat cost of one generated animation scene (fal.ai Kling Standard, ~5s clip).
export const ANIMATION_USD_PER_SCENE = 0.25;

export const estimateSegmentSeconds = (text: string): number =>
  Math.max(1, text.trim().length / CHARS_PER_SEC);

export const estimateEpisode = (segments: Segment[]) => {
  const audio_secs = segments.reduce(
    (sum, segment) => sum + estimateSegmentSeconds(segment.text),
    0,
  );
  // Scenes: animation render + (optional) narration TTS, no lip-sync.
  // Dialogue: TTS + lip-sync over the audio length.
  const cost_usd = segments.reduce((sum, segment) => {
    const secs = estimateSegmentSeconds(segment.text);
    if (segment.kind === "scene") {
      const narrationCost = segment.text.trim() ? TTS_USD_PER_SEG : 0;
      return sum + ANIMATION_USD_PER_SCENE + narrationCost;
    }
    return sum + secs * LIPSYNC_USD_PER_SEC + TTS_USD_PER_SEG;
  }, 0);
  return {
    audio_secs,
    cost_usd,
    segments: segments.length,
  };
};

export const safeSlug = (text: string): string => {
  const normalized = text
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
  return normalized || "character";
};

export const getCandidateImageUrl = (slug: string, index: number): string => {
  const encoded = encodeURIComponent(`${slug}+${index}`);
  return `https://via.placeholder.com/360x360.png?text=${encoded}`;
};
