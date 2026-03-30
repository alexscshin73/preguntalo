"use client";

import { ManualsShell } from "../../components/manuals/manuals-shell";
import SiteHeader from "../../components/site-header";
import { useUiLanguage } from "../../components/ui-language";

export default function ManualsPage() {
  const { locale, toggleLocale } = useUiLanguage();

  return (
    <>
      <SiteHeader lang={locale} onToggleLanguage={toggleLocale} />
      <ManualsShell />
    </>
  );
}
