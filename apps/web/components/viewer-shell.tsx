"use client";

import { useEffect, useMemo, useState } from "react";
import { apiUrl } from "../lib/api";
import { uiText } from "./i18n/ui-text";
import SiteHeader from "./site-header";
import { useUiLanguage } from "./ui-language";
import styles from "./viewer-shell.module.css";

type ViewerShellProps = {
  manualId: string;
  page: string;
  section: string;
  versionId: string;
};

type ViewerPageDetail = {
  manualId: string;
  manualTitle: string;
  versionId: string;
  versionLabel: string;
  pageNumber: number;
  totalPages: number;
  extractedText: string;
  sectionId?: string | null;
  sectionHeading?: string | null;
};

export function ViewerShell({ manualId, page, section, versionId }: ViewerShellProps) {
  const { locale, toggleLocale } = useUiLanguage();
  const copy = uiText[locale].viewer;
  const [detail, setDetail] = useState<ViewerPageDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [frameLoading, setFrameLoading] = useState(true);

  const pageNumber = useMemo(() => {
    const parsed = Number.parseInt(page, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [page]);

  const documentUrl = useMemo(() => {
    if (!pageNumber) {
      return "";
    }

    return `${apiUrl(
      `/api/v1/manuals/${manualId}/versions/${versionId}/download`
    )}#page=${pageNumber}&zoom=page-fit&view=FitV&pagemode=none&navpanes=0`;
  }, [manualId, pageNumber, versionId]);

  useEffect(() => {
    if (!pageNumber) {
      setError(copy.emptyText);
      setDetail(null);
      setLoading(false);
      return;
    }

    let active = true;

    async function loadViewerPage() {
      setLoading(true);
      setError(null);

      try {
        const query = section && section !== "-" ? `?section_id=${encodeURIComponent(section)}` : "";
        const response = await fetch(
          apiUrl(`/api/v1/manuals/${manualId}/versions/${versionId}/pages/${pageNumber}${query}`)
        );

        if (!response.ok) {
          throw new Error(`Viewer page request failed with ${response.status}`);
        }

        const payload = (await response.json()) as ViewerPageDetail;
        if (!active) return;
        setDetail(payload);
      } catch (viewerError) {
        if (!active) return;
        setDetail(null);
        setError(viewerError instanceof Error ? viewerError.message : copy.emptyText);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadViewerPage();

    return () => {
      active = false;
    };
  }, [copy.emptyText, manualId, pageNumber, section, versionId]);

  useEffect(() => {
    setFrameLoading(true);
  }, [documentUrl]);

  return (
    <>
      <SiteHeader lang={locale} onToggleLanguage={toggleLocale} />

      <main className={styles.shell}>
        <div className={styles.frame}>
          <section className={styles.hero}>
            <div className={styles.eyebrow}>{copy.eyebrow}</div>
            <h1 className={styles.title}>{copy.title}</h1>
            <p className={styles.copy}>{copy.copy}</p>
          </section>

          <section className={styles.metaPanel}>
            <div className={styles.pill}>
              {copy.manual} {detail?.manualTitle ?? manualId}
            </div>
            <div className={styles.pill}>
              {copy.version} {detail?.versionLabel ?? versionId}
            </div>
            <div className={styles.pill}>
              {copy.page} {detail?.pageNumber ?? page}
            </div>
            <div className={styles.pill}>
              {copy.section} {detail?.sectionHeading ?? section}
            </div>
          </section>

          <section className={styles.viewerCard}>
            <div className={styles.cardHeader}>
              <h2>{copy.originalTitle}</h2>
              <div className={styles.headerActions}>
                <span>
                  {copy.page} {detail?.pageNumber ?? page}
                  {detail?.totalPages ? ` / ${detail.totalPages}` : ""}
                </span>
                {documentUrl ? (
                  <a
                    className={styles.openButton}
                    href={documentUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {copy.openOriginal}
                  </a>
                ) : null}
              </div>
            </div>

            {loading ? (
              <div className={styles.emptyState}>{copy.loading}</div>
            ) : error ? (
              <div className={styles.emptyState}>{error}</div>
            ) : documentUrl ? (
              <div className={styles.documentFrameWrap}>
                <iframe
                  key={documentUrl}
                  className={styles.documentFrame}
                  src={documentUrl}
                  title={`${detail?.manualTitle ?? manualId} original page ${detail?.pageNumber ?? page}`}
                  loading="lazy"
                  onLoad={() => setFrameLoading(false)}
                />
                {frameLoading ? <div className={styles.frameOverlay}>{copy.loading}</div> : null}
              </div>
            ) : (
              <div className={styles.emptyState}>{copy.emptyText}</div>
            )}
          </section>
        </div>
      </main>
    </>
  );
}
