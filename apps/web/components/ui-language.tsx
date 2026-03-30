"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type UiLang = "ko" | "es";

type UiLanguageContextValue = {
  locale: UiLang;
  setLocale: (locale: UiLang) => void;
  toggleLocale: () => void;
};

const UiLanguageContext = createContext<UiLanguageContextValue | null>(null);

export function UiLanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<UiLang>("ko");

  const toggleLocale = useCallback(() => {
    setLocale((prev) => (prev === "ko" ? "es" : "ko"));
  }, []);

  const value = useMemo<UiLanguageContextValue>(
    () => ({
      locale,
      setLocale,
      toggleLocale,
    }),
    [locale, toggleLocale]
  );

  return (
    <UiLanguageContext.Provider value={value}>
      {children}
    </UiLanguageContext.Provider>
  );
}

export function useUiLanguage() {
  const context = useContext(UiLanguageContext);

  if (!context) {
    throw new Error("useUiLanguage must be used within UiLanguageProvider");
  }

  return context;
}
