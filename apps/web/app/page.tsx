"use client";

import SiteHeader from "@/components/site-header";
import { SearchShell } from "@/components/home/search-shell";
import { useUiLanguage } from "@/components/ui-language";

export default function HomePage() {
  const { locale, toggleLocale } = useUiLanguage();

  return (
    <>
      <SiteHeader lang={locale} onToggleLanguage={toggleLocale} />
      <SearchShell />
    </>
  );
}
