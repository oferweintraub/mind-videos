import { createStore } from 'redux';
import { reducer } from './reducers';

export const idstore = createStore(reducer);
