import type { APIKeys } from '../types';
import { SET_API_KEY, SET_SHARE_KEYS, LOAD_SETTINGS, RESET_SETTINGS } from './settingsActions';

export type SettingsState = {
  apiKeys: APIKeys;
  shareKeys: boolean;
};

const initialState: SettingsState = {
  apiKeys: {
    fal: '',
    elevenlabs: '',
    google: '',
  },
  shareKeys: false,
};

export default function settings(state: SettingsState = initialState, action: any): SettingsState {
  switch (action.type) {
    case SET_API_KEY:
      return {
        ...state,
        apiKeys: {
          ...state.apiKeys,
          [action.key]: action.value,
        },
      };
    case SET_SHARE_KEYS:
      return {
        ...state,
        shareKeys: action.value,
      };
    case LOAD_SETTINGS:
      return {
        ...state,
        ...action.settings,
      };
    case RESET_SETTINGS:
      return initialState;
    default:
      return state;
  }
}
