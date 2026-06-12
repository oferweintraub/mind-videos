import { SET_PROJECTS, SET_CURRENT_PROJECT, RESET_PROJECTS } from './projectsActions';

export type SavedProjectMeta = {
  name: string;
  updated_at?: number;
};

export type ProjectsState = {
  // Index of the logged-in user's saved projects (names + timestamps).
  // The full project data lives in the working app state and on the server.
  list: SavedProjectMeta[];
  // Name of the project currently loaded into the editor, if any.
  current: string | null;
};

const initialState: ProjectsState = {
  list: [],
  current: null,
};

export default function projects(state: ProjectsState = initialState, action: any): ProjectsState {
  switch (action.type) {
    case SET_PROJECTS:
      return { ...state, list: Array.isArray(action.list) ? action.list : [] };
    case SET_CURRENT_PROJECT:
      return { ...state, current: action.name ?? null };
    case RESET_PROJECTS:
      return initialState;
    default:
      return state;
  }
}
