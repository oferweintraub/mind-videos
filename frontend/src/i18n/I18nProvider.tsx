import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { translations, Lang } from './dictionary';

interface I18nContextProps {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

export const I18nContext = createContext<I18nContextProps>({
  lang: 'en',
  setLang: () => {},
  t: (key) => translations.en[key] || key,
});

export const I18nProvider = ({ children }: { children: ReactNode }) => {
  const [lang, setLangState] = useState<Lang>(() => {
    try {
      return (localStorage.getItem('mindvideo_lang') as Lang) || 'he';
    } catch {
      return 'he';
    }
  });

  // Hebrew is right-to-left; mirror the whole document accordingly.
  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr';
  }, [lang]);

  const t = (key: string, vars?: Record<string, string | number>) => {
    let template = translations[lang][key] || translations.en[key] || key;
    if (!vars) return template;
    return Object.entries(vars).reduce(
      (value, [name, replacement]) => value.split(`{${name}}`).join(String(replacement)),
      template,
    );
  };

  const setLang = (next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem('mindvideo_lang', next);
    } catch {}

    if (typeof window !== 'undefined') {
      let locale = 'en-US';
      if (next === 'he') locale = 'he-IL';
      else if (next === 'es') locale = 'es-ES';
      else if (next === 'fr') locale = 'fr-FR';
      else if (next === 'de') locale = 'de-DE';
      else if (next === 'el') locale = 'el-GR';
      (window as any).__mindvideo_locale = locale;
    }
  };

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
};

export const useI18n = () => useContext(I18nContext);
