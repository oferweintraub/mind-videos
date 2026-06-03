export type DevModelInputs = Record<string, any>;

export const DEFAULT_INPUTS: DevModelInputs = {
  landPricePSF: 0,
  netRentableAreaSF: 0,
  siteSF: 0,
};

export const EMPTY_INPUTS: DevModelInputs = {
  ...DEFAULT_INPUTS,
};

export type Contact = {
  id: string;
  name: string;
  title: string;
  phone: string;
};
