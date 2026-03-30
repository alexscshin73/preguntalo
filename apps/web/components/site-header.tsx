"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { uiText } from "./i18n/ui-text";
import styles from "./site-header.module.css";

type SiteHeaderProps = {
  lang: "ko" | "es";
  onToggleLanguage: () => void;
};

export default function SiteHeader({
  lang,
  onToggleLanguage,
}: SiteHeaderProps) {
  const pathname = usePathname();
  const copy = uiText[lang].header;

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.leftCluster}>
          <div className={styles.tooltipWrapper}>
            <Link href="/" className={styles.brand}>
              <Image
                src="/assets/PreguntaLo-tight.png"
                alt="PreguntaLo"
                width={120}
                height={78}
                className={styles.brandLogo}
                priority
              />
            </Link>
            <span className={styles.tooltip}>{copy.tooltipHome}</span>
          </div>

          <div className={styles.actions}>
            <div className={styles.tooltipWrapper}>
              <Link
                href="/manuals"
                className={`${styles.menuLink} ${pathname.startsWith("/manuals") ? styles.menuLinkActive : ""}`}
                aria-label={copy.manuals}
              >
                <Image
                  src="/assets/header-manual.png"
                  alt=""
                  width={45}
                  height={45}
                  className={styles.actionIcon}
                />
              </Link>
              <span className={styles.tooltip}>{copy.tooltipManuals}</span>
            </div>

            <div className={styles.tooltipWrapper}>
              <button
                type="button"
                className={styles.langToggle}
                onClick={onToggleLanguage}
                aria-label={copy.switchLang}
              >
                <Image
                  src="/assets/header-language.png"
                  alt=""
                  width={45}
                  height={45}
                  className={styles.actionIcon}
                />
              </button>
              <span className={styles.tooltip}>{copy.tooltipLanguage}</span>
            </div>
          </div>
        </div>

        <div
          className={`${styles.tagline} ${
            lang === "ko" ? styles.taglineKo : styles.taglineEs
          }`}
        >
          {copy.tagline}
        </div>
      </div>
    </header>
  );
}
