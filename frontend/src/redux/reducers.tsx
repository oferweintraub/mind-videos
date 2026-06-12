import { combineReducers } from 'redux';
import system from './systemReducer';
import settings from './settingsReducer';
import projects from './projectsReducer';

export const reducer = combineReducers({ system, settings, projects });
