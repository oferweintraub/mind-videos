export const convertInputs = (inputs: Record<string, any>, from: string, to: string): Record<string, any> => {
  return { ...inputs, convertedFrom: from, convertedTo: to };
};
