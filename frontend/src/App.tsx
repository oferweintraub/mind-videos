// TypeScript may complain about missing type declarations for CSS side-effect imports.
// Ignore the next line so the build can proceed without a .d.ts for CSS files.
// @ts-ignore
import "./theme/styles/allStyles.css";
import { useEffect, useMemo, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { AppState, AuthUser, Character, Candidate, RecentProject, RenderResult, Segment, VoiceSample } from "./types";
import { StepIndicator } from "./components/StepIndicator";
import { Sidebar } from "./components/Sidebar";
import { CastStep } from "./components/CastStep";
import { ScriptStep } from "./components/ScriptStep";
import { VoiceStep } from "./components/VoiceStep";
import { RenderStep } from "./components/RenderStep";
import { PreviewStep } from "./components/PreviewStep";
import { CharacterLibrary } from "./components/CharacterLibrary";
import { AuthScreen } from "./components/AuthScreen";
import { estimateEpisode, safeSlug } from "./utils";
import { idstore } from "./redux/IDStore";
import { SET_API_KEY, SET_SHARE_KEYS, LOAD_SETTINGS, RESET_SETTINGS } from "./redux/settingsActions";
import {
  loadEncryptedSettingsFromLocalStorage,
  saveEncryptedSettingsToLocalStorage,
  downloadEncryptedSettingsFile,
} from "./utils/cryptoUtils";
import { useI18n } from "./i18n/I18nProvider";

const STORAGE_KEY = "mind-video-app-state";

type RootState = ReturnType<typeof idstore.getState>;

const initialState: AppState = {
  step: 1,
  title: "",
  cast: [],
  segments: [],
  voiceSamples: {},
  result: null,
  apiKeys: { fal: "", elevenlabs: "", google: "" },
  authUser: null,
  shareKeys: false,
  recentProjects: [],
  projectId: null,
};

const DEMO_CHARACTERS: Character[] = [
  {
    slug: "anchor_female",
    displayName: "Anchor Female",
    description: "A confident news anchor with strong eye contact.",
    style: "lego",
    voiceId: "FGY2WhTYpPnrIDTdsKH5",
    voiceName: "Laura",
    tempo: 1.25,
    imageUrl: "https://via.placeholder.com/360x360.png?text=Anchor+Female",
  },
  {
    slug: "anchor_male",
    displayName: "Anchor Male",
    description: "A dramatic male anchor with a serious expression.",
    style: "muppet",
    voiceId: "IKne3meq5aSn9XLyUdCD",
    voiceName: "Charlie",
    tempo: 1.25,
    imageUrl: "https://via.placeholder.com/360x360.png?text=Anchor+Male",
  },
  {
    slug: "eden",
    displayName: "Eden",
    description: "A quiet young character with a thoughtful gaze.",
    style: "pixar",
    voiceId: "cgSgspJ2msm6clMCkdW9",
    voiceName: "Jessica",
    tempo: 1.0,
    imageUrl: "https://via.placeholder.com/360x360.png?text=Eden",
  },
];

const DEMO_SEGMENTS: Segment[] = [
  {
    character: "anchor_female",
    text: "אני מאוהבת, איזה מנהיג חזק, איזה מנהיג דגול יש לנו, קרה לנו נס!",
  },
  {
    character: "anchor_male",
    text: "לגמרי! לא משאירים אנשים מאחור, זה לא יקרה במשמרת שלנו!",
  },
  {
    character: "eden",
    text: "אמא, הוא אמר שלא משאירים אנשים מאחור, אבל את החטופים השארנו מאחור.",
  },
];

function loadState(): AppState {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (!saved) return initialState;
    return { ...initialState, ...(JSON.parse(saved) as Partial<AppState>) };
  } catch {
    return initialState;
  }
}

function App() {
  const [state, setState] = useState<AppState>(() => loadState());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [authPassword, setAuthPassword] = useState<string | null>(null);
  const dispatch = useDispatch();
  const settings = useSelector((state: RootState) => state.settings);
  const { t } = useI18n();

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const summary = useMemo(() => estimateEpisode(state.segments), [state.segments]);

  const updateApiKey = (key: keyof AppState["apiKeys"], value: string) => {
    dispatch({ type: SET_API_KEY, key, value });
  };

  const updateShareKeys = (value: boolean) => {
    dispatch({ type: SET_SHARE_KEYS, value });
  };

  const resetProject = () => {
    setState((current) => ({
      ...initialState,
      authUser: current.authUser,
      projectId: current.projectId,
      recentProjects: current.recentProjects,
    }));
  };

  const loadDemo = () => {
    setState((current) => ({
      ...current,
      step: 2,
      title: "Hostages",
      cast: DEMO_CHARACTERS,
      segments: DEMO_SEGMENTS,
      result: null,
    }));
  };

  const persistUserSettings = async (email: string, password: string) => {
    try {
      const payload = {
        apiKeys: settings.apiKeys,
        shareKeys: settings.shareKeys,
      };
      const cipher = await saveEncryptedSettingsToLocalStorage(email, password, payload);
      await downloadEncryptedSettingsFile(email, cipher);
    } catch (error) {
      console.error('Unable to save encrypted settings:', error);
    }
  };

  const applySettings = async (): Promise<boolean> => {
    if (!state.authUser || !authPassword) return false;
    try {
      await saveEncryptedSettingsToLocalStorage(state.authUser.email, authPassword, {
        apiKeys: settings.apiKeys,
        shareKeys: settings.shareKeys,
      });
      return true;
    } catch (error) {
      console.error('Unable to apply settings:', error);
      return false;
    }
  };

  const loadUserSettings = async (email: string, password: string) => {
    try {
      const loaded = await loadEncryptedSettingsFromLocalStorage(email, password);
      if (loaded && typeof loaded === 'object' && 'apiKeys' in loaded) {
        dispatch({ type: LOAD_SETTINGS, settings: loaded });
      }
    } catch (error) {
      console.warn('Unable to load encrypted settings for user:', error);
    }
  };

  const addOrUpdateCharacter = (character: Character) => {
    setState((current) => {
      const existingIndex = current.cast.findIndex((item) => item.slug === character.slug);
      const cast = [...current.cast];
      if (existingIndex >= 0) {
        cast[existingIndex] = character;
      } else {
        cast.push(character);
      }
      return { ...current, cast };
    });
  };

  const removeCharacter = (slug: string) => {
    setState((current) => ({
      ...current,
      cast: current.cast.filter((character) => character.slug !== slug),
      segments: current.segments.filter((segment) => segment.character !== slug),
    }));
  };

  const addSegment = (character: string) => {
    setState((current) => ({
      ...current,
      segments: [...current.segments, { character, text: "", kind: "dialogue" }],
    }));
  };

  const addScene = (character: string) => {
    setState((current) => ({
      ...current,
      segments: [
        ...current.segments,
        { character, text: "", kind: "scene", animationPrompt: "" },
      ],
    }));
  };

  const updateSegment = (index: number, updates: Partial<Segment>) => {
    setState((current) => {
      const segments = [...current.segments];
      segments[index] = { ...segments[index], ...updates };
      return { ...current, segments };
    });
  };

  const moveSegment = (index: number, delta: number) => {
    setState((current) => {
      const segments = [...current.segments];
      const target = index + delta;
      if (target < 0 || target >= segments.length) return current;
      [segments[index], segments[target]] = [segments[target], segments[index]];
      return { ...current, segments };
    });
  };

  const removeSegment = (index: number) => {
    setState((current) => ({
      ...current,
      segments: current.segments.filter((_, idx) => idx !== index),
    }));
  };

  const setStep = (step: 1 | 2 | 3 | 4 | 5) => {
    // Keep the render result when sitting on Render/Preview; clear it when
    // navigating back to edit steps so a stale preview can't resurface.
    setState((current) => ({
      ...current,
      step,
      result: step === 4 || step === 5 ? current.result : null,
    }));
  };

  const setVoiceSample = (slug: string, sample: VoiceSample | null) => {
    setState((current) => {
      const voiceSamples = { ...current.voiceSamples };
      if (sample) {
        voiceSamples[slug] = sample;
      } else {
        delete voiceSamples[slug];
      }
      return { ...current, voiceSamples };
    });
  };

  const updateVoiceSampleClonedId = (slug: string, clonedVoiceId: string) => {
    setState((current) => {
      const existing = current.voiceSamples[slug];
      if (!existing) return current;
      return {
        ...current,
        voiceSamples: {
          ...current.voiceSamples,
          [slug]: { ...existing, clonedVoiceId },
        },
      };
    });
  };

  const completeRender = (slug: string, videoPath?: string) => {
    setState((current) => ({
      ...current,
      result: {
        elapsed: Math.floor(Math.random() * 25) + 40,
        cost: summary.cost_usd,
        title: current.title || "Untitled",
        slug,
        videoUrl: videoPath || undefined,
      },
      step: 5,
    }));
  };

  const loginUser = async (user: AuthUser, password: string) => {
    setAuthPassword(password);
    // Fresh login: drop any state cached for a previous user (cast, segments,
    // voice samples, current project, recents). Clear the persisted blob too
    // so a page reload mid-login can't resurrect it.
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {}
    setState({ ...initialState, authUser: user });
    dispatch({ type: RESET_SETTINGS });
    await loadUserSettings(user.email, password);
  };

  const logoutUser = async () => {
    if (state.authUser && authPassword) {
      await persistUserSettings(state.authUser.email, authPassword);
    }
    setAuthPassword(null);
    setState((current) => ({ ...current, authUser: null }));
  };

  const toggleSettings = () => setSettingsOpen((current) => !current);
  const closeSettings = () => setSettingsOpen(false);

  const importProject = (project: AppState) => {
    setState(project);
  };

  const exportProject = () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "mind-video-project.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  const projectTitle = state.title || t("untitledEpisode");
  const projectSlug = safeSlug(projectTitle || "untitled");

  if (!state.authUser) {
    return (
      <div className="app-shell">
        <main className="content">
          <AuthScreen onLogin={loginUser} />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <main className="content">
        <div className="topbar">
          <header className="page-header">
            <div>
              <p className="eyebrow">🎬 {t("appName")}</p>
              <h1>{t("appSubtitle")}</h1>
            </div>
          </header>
          <div className="topbar-labels">
            <p className="eyebrow">{t("signedInAs")}</p>
            <div className="topbar-user">{state.authUser?.email || t("unknownUser")}</div>
          </div>
          <div className="topbar-actions">
            <button type="button" className="icon-button" onClick={toggleSettings} aria-label={t("openSettings")}> 
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09c.12-.38.35-.73.67-1.01A1.65 1.65 0 0 0 5.6 8.6a1.65 1.65 0 0 0 .33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09c.12.38.35.73.67 1.01a1.65 1.65 0 0 0 1.82.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09c-.12.38-.35.73-.67 1.01z" />
            </svg>
          </button>
            <button type="button" className="secondary" onClick={logoutUser}>
              {t("logout")}
            </button>
          </div>
        </div>
        <div className="workspace">
        <StepIndicator
          step={state.step}
          labels={[t("cast"), t("script"), t("voice"), t("render"), t("preview")]}
          onStepChange={(n) => {
            if (n === 1 || n === 2 || n === 3 || n === 4 || n === 5) setStep(n);
          }}
        />
        <div className="step-panel">
          {state.step === 1 && (
            <CastStep
              state={state}
              onAddCharacter={addOrUpdateCharacter}
              onRemoveCharacter={removeCharacter}
              onLoadDemo={loadDemo}
              onContinue={() => setStep(2)}
            />
          )}
          {state.step === 2 && (
            <ScriptStep
              state={state}
              onSetTitle={(title) => setState((current) => ({ ...current, title }))}
              onAddSegment={addSegment}
              onAddScene={addScene}
              onUpdateSegment={updateSegment}
              onMoveSegment={moveSegment}
              onRemoveSegment={removeSegment}
              onBack={() => setStep(1)}
              onContinue={() => setStep(3)}
            />
          )}
          {state.step === 3 && (
            <VoiceStep
              state={state}
              onSetVoiceSample={setVoiceSample}
              onBack={() => setStep(2)}
              onContinue={() => setStep(4)}
            />
          )}
          {state.step === 4 && (
            <RenderStep
              state={state}
              onBack={() => setStep(3)}
              onVoiceCloned={updateVoiceSampleClonedId}
              onRenderComplete={completeRender}
            />
          )}
          {state.step === 5 && (
            <PreviewStep
              state={state}
              onBack={() => setStep(4)}
              onNewProject={resetProject}
            />
          )}
        </div>
        </div>
        <CharacterLibrary cast={state.cast} onAddCharacter={addOrUpdateCharacter} />
      </main>
      {settingsOpen && <div className="sidebar-backdrop" onClick={closeSettings} />}
      {settingsOpen && (
        <Sidebar
          apiKeys={settings.apiKeys}
          shareKeys={settings.shareKeys}
          recentProjects={state.recentProjects}
          projectId={state.projectId}
          onUpdateKey={updateApiKey}
          onApply={applySettings}
          onToggleShareKeys={updateShareKeys}
          onReset={resetProject}
          onExport={exportProject}
          onImport={importProject}
          onLoadDemo={loadDemo}
          authUser={state.authUser}
          onLogout={logoutUser}
          onClose={closeSettings}
        />
      )}
    </div>
  );
}

export default App;
