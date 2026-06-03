import { SET_NEXT_PAGE, SET_PREVIOUS_PAGE, GET_PAGE, SET_IS_MOBILE } from './systemActions';

type State = {
  currentPage: number;
  isMobile: boolean;
};

const PAGE_COUNT = 9;

const initialState: State = {
  currentPage: 0,
  isMobile: false,
};

const system = (state: State = initialState, action: any) => {
  switch (action.type) {
    case SET_NEXT_PAGE.type:
      return { ...state, currentPage: Math.min(PAGE_COUNT - 1, state.currentPage + 1) };
    case SET_PREVIOUS_PAGE.type:
      return { ...state, currentPage: Math.max(0, state.currentPage - 1) };
    case 'SET_PAGE':
      return { ...state, currentPage: Math.max(0, Math.min(PAGE_COUNT - 1, action.value)) };
    case SET_IS_MOBILE:
      return { ...state, isMobile: action.value };
    case GET_PAGE.type:
    default:
      return state;
  }
};

export default system;
