import { en } from './en';
import { he } from './he';
import { es } from './es';
import { fr } from './fr';
import { de } from './de';
import { el } from './el';

export const translations = { en, he, es, fr, de, el } as const;

export type Lang = keyof typeof translations;
