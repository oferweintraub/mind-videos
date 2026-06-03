import { combineReducers } from 'redux';
import system from './systemReducer';
import settings from './settingsReducer';

export const reducer = combineReducers({ system, settings });
