export type Character = {
  slug: string;
  displayName: string;
  description: string;
  style: string;
  voiceId: string;
  voiceName: string;
  tempo: number;
  imageUrl: string;
  public?: boolean;  // whether character is in public library
};

export type Segment = {
  character: string;          // for a scene: the narrator's voice
  text: string;               // dialogue line OR scene narration
  background?: string;
  kind?: "dialogue" | "scene";
  animationPrompt?: string;   // scene only — text-to-video prompt
  style?: string;             // scene only — visual style (lego, pixar, …)
};

export type RenderResult = {
  elapsed: number;
  cost: number;
  title: string;
  slug: string;
  videoUrl?: string;
};

export type LibraryVideo = {
  slug: string;
  title: string;
  videoUrl: string;
  createdAt: number;
};

export type APIKeys = {
  fal: string;
  elevenlabs: string;
  google: string;
};

export type AuthUser = {
  email: string;
};

export type RecentProject = {
  id: string;
  title: string;
};

export type VoiceSample = {
  fileName: string;
  mimeType: string;
  dataUrl: string;
  clonedVoiceId?: string;
};

export type AppState = {
  step: 1 | 2 | 3 | 4 | 5;
  title: string;
  cast: Character[];
  segments: Segment[];
  voiceSamples: Record<string, VoiceSample>;
  result: RenderResult | null;
  apiKeys: APIKeys;
  authUser: AuthUser | null;
  shareKeys: boolean;
  recentProjects: RecentProject[];
  projectId: string | null;
};

export type Candidate = {
  idx: number;
  style: string;
  imageUrl: string;
};
