"use client";

import { FormEvent, KeyboardEvent, useEffect, useState } from "react";

import { apiUrl } from "../../lib/api";
import { uiText } from "../i18n/ui-text";
import { useUiLanguage } from "../ui-language";
import styles from "./search-shell.module.css";

type SearchResultItem = {
  sectionId: string;
  manualId: string;
  manualTitle: string;
  versionId: string;
  versionLabel: string;
  heading: string;
  snippet: string;
  score: number;
  pageStart: number;
  pageEnd: number;
  detailUrl: string;
  tags: string[];
};

type AnswerCitationItem = {
  sectionId: string;
  manualId: string;
  manualTitle: string;
  versionId: string;
  versionLabel: string;
  heading: string;
  pageStart: number;
  pageEnd: number;
  detailUrl: string;
};

type AnswerResponse = {
  queryLanguage: string;
  queryTags: string[];
  answer: string;
  answerSource: string;
  citations: AnswerCitationItem[];
  results: SearchResultItem[];
};

type PopularQueryTagItem = {
  tag: string;
  queryCount: number;
};

type PopularQueryTagResponse = {
  items: PopularQueryTagItem[];
};

const MAX_SEARCH_TAGS = 5;

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);

  if (!response.ok) {
    let detail = `Request failed with ${response.status}`;

    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = String(payload.detail);
      }
    } catch {
      // Ignore non-JSON error bodies.
    }

    throw new Error(detail);
  }

  return (await response.json()) as T;
}

function formatAnswerText(text: string): string {
  return text.replace(/(?<!\d)([.?!])\s+/g, "$1\n");
}

function splitAnswerLines(text: string): string[] {
  return formatAnswerText(text)
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function truncateCitationLabel(label: string): string {
  const trimmed = label.trim();
  if (trimmed.length <= 15) {
    return trimmed;
  }
  return `${trimmed.slice(0, 15)}...`;
}

function citationLabel(citation: AnswerCitationItem): string {
  return truncateCitationLabel(citation.versionLabel || citation.manualTitle);
}

function citationOriginalUrl(citation: AnswerCitationItem): string {
  return `${apiUrl(
    `/api/v1/manuals/${citation.manualId}/versions/${citation.versionId}/download`
  )}#page=${Math.max(1, citation.pageStart)}&zoom=page-fit&view=FitV&pagemode=none&navpanes=0`;
}

function normalizeTag(raw: string): string {
  return raw.trim().replace(/^#+/, "").replace(/\s+/g, "").toLowerCase();
}

function padTagSlots(tags: string[]) {
  return Array.from({ length: MAX_SEARCH_TAGS }, (_, index) => tags[index] ?? "");
}

function dedupeCitations(citations: AnswerCitationItem[]): AnswerCitationItem[] {
  const seen = new Set<string>();
  const unique: AnswerCitationItem[] = [];

  for (const citation of citations) {
    const key = `${citation.manualId}:${citation.versionId}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(citation);
  }

  return unique;
}

function isMeaningfulHeading(heading: string | null | undefined): boolean {
  if (!heading) {
    return false;
  }

  const trimmed = heading.replace(/\s+/g, " ").trim();
  if (!trimmed) {
    return false;
  }

  if (/^\d+(\.\d+)*$/.test(trimmed)) {
    return false;
  }

  if (trimmed.length < 3) {
    return false;
  }

  return /[가-힣A-Za-z]/.test(trimmed);
}

export function SearchShell() {
  const { locale } = useUiLanguage();
  const copy = uiText[locale].search;

  const [question, setQuestion] = useState("");
  const [selectedTagSlots, setSelectedTagSlots] = useState<string[]>(padTagSlots([]));
  const [popularTags, setPopularTags] = useState<string[]>([]);
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [answerText, setAnswerText] = useState("");
  const [citations, setCitations] = useState<AnswerCitationItem[]>([]);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const topResult = results[0] ?? null;
  const answerLines = splitAnswerLines(answerText);
  const uniqueCitations = dedupeCitations(citations);
  const selectedTags = Array.from(
    new Set(
      selectedTagSlots
        .map((tag) => normalizeTag(tag))
        .filter((tag) => tag.length > 0)
    )
  ).slice(0, MAX_SEARCH_TAGS);

  useEffect(() => {
    let ignore = false;

    async function loadPopularTags() {
      try {
        const payload = await requestJson<PopularQueryTagResponse>("/api/v1/search/tags/popular");
        if (ignore) {
          return;
        }
        setPopularTags(
          (payload.items ?? [])
            .map((item) => normalizeTag(item.tag))
            .filter((tag) => tag.length > 0)
        );
      } catch {
        if (!ignore) {
          setPopularTags([]);
        }
      }
    }

    void loadPopularTags();
    return () => {
      ignore = true;
    };
  }, []);

  function addTag(rawTag: string) {
    const normalized = normalizeTag(rawTag);
    if (!normalized) {
      return;
    }

    setSelectedTagSlots((current) => {
      const currentNormalized = current.map((tag) => normalizeTag(tag));
      if (currentNormalized.includes(normalized)) {
        return current;
      }

      const emptyIndex = currentNormalized.findIndex((tag) => !tag);
      if (emptyIndex === -1) {
        return current;
      }

      return current.map((tag, index) => (index === emptyIndex ? normalized : tag));
    });
  }

  function updateTagSlot(index: number, rawValue: string) {
    setSelectedTagSlots((current) =>
      current.map((tag, currentIndex) =>
        currentIndex === index ? rawValue.replace(/^#+/, "").slice(0, 24) : tag
      )
    );
  }

  function commitTagSlot(index: number) {
    setSelectedTagSlots((current) => {
      const next = [...current];
      const normalized = normalizeTag(next[index]);

      if (!normalized) {
        next[index] = "";
        return next;
      }

      const duplicateIndex = next.findIndex(
        (tag, currentIndex) => currentIndex !== index && normalizeTag(tag) === normalized
      );
      if (duplicateIndex !== -1) {
        next[index] = "";
        return next;
      }

      next[index] = normalized;
      return next;
    });
  }

  function removeTagAt(index: number) {
    setSelectedTagSlots((current) =>
      current.map((tag, currentIndex) => (currentIndex === index ? "" : tag))
    );
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextQuestion = question.trim();
    if (!nextQuestion) {
      return;
    }

    setSubmittedQuestion(nextQuestion);
    setIsSearching(true);
    setSearchError(null);

    try {
      const payload = await requestJson<AnswerResponse>("/api/v1/answer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: nextQuestion,
          language: locale,
          tags: selectedTags,
          topK: 5,
          manualIds: [],
        }),
      });

      setAnswerText(payload.answer ?? "");
      setCitations(payload.citations ?? []);
      setResults(payload.results ?? []);
    } catch (error) {
      setAnswerText("");
      setCitations([]);
      setResults([]);
      setSearchError(error instanceof Error ? error.message : "Failed to search");
    } finally {
      setIsSearching(false);
    }
  }

  function handleQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }

    event.preventDefault();
    if (isSearching) {
      return;
    }

    event.currentTarget.form?.requestSubmit();
  }

  return (
    <main className={styles.shell}>
      <section className={styles.hero}>
        <form className={styles.inputGroup} onSubmit={handleAsk}>
          <section className={styles.inputSection}>
            <label className={styles.sectionLabel} htmlFor="question-input">
              {copy.questionLabel}
            </label>
            {popularTags.length > 0 ? (
              <div className={styles.tagBlock}>
                <div className={styles.tagList}>
                  {popularTags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      className={styles.popularTagButton}
                      onClick={() => addTag(tag)}
                    >
                      #{tag}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            <div className={styles.questionRow}>
              <textarea
                id="question-input"
                className={styles.questionField}
                value={question}
                placeholder={copy.questionPlaceholder}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={handleQuestionKeyDown}
              />
              <button className={styles.primaryButton} type="submit">
                {copy.askButton}
              </button>
            </div>
            <div className={styles.tagEditor}>
              <label className={styles.tagLabel} htmlFor="tag-input">
                {copy.tagLabel}
              </label>
              <div className={styles.searchTagScroller}>
                {selectedTagSlots.map((tag, index) => (
                  <div
                    key={`search-tag-${index}`}
                    className={styles.searchTagChip}
                    title={tag.trim() || undefined}
                  >
                    <input
                      id={index === 0 ? "tag-input" : undefined}
                      className={styles.searchTagInput}
                      value={tag}
                      placeholder=""
                      maxLength={24}
                      title={tag.trim() || undefined}
                      onChange={(event) => updateTagSlot(index, event.target.value)}
                      onBlur={() => commitTagSlot(index)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          commitTagSlot(index);
                          (event.currentTarget as HTMLInputElement).blur();
                        }
                      }}
                    />
                    {tag.trim() ? (
                      <button
                        type="button"
                        className={styles.searchTagRemove}
                        onClick={() => removeTagAt(index)}
                        aria-label={`remove-search-tag-${index + 1}`}
                      >
                        ×
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </form>

        <section className={styles.outputSection}>
          <div className={styles.sectionLabel}>{copy.answerTitle}</div>
          <div className={styles.outputPanel}>
            {!submittedQuestion ? (
              <p className={styles.outputCopy}>{copy.answerPlaceholder}</p>
            ) : isSearching ? (
              <p className={styles.outputCopy}>{copy.loadingAnswer}</p>
            ) : searchError ? (
              <p className={styles.outputCopy}>{searchError}</p>
            ) : answerText ? (
              <>
                {topResult && isMeaningfulHeading(topResult.heading) ? (
                  <p className={styles.answerHeading}>{topResult.heading}</p>
                ) : null}
                <div className={styles.answerBody}>
                  {answerLines.map((line, index) => {
                    const inlineCitations =
                      index === 0
                        ? uniqueCitations
                        : [];

                    return (
                      <p key={`${line}-${index}`} className={`${styles.outputCopy} ${styles.answerLine}`}>
                        <span>{line}</span>
                        {inlineCitations.length > 0 ? (
                          <span className={styles.inlineCitationGroup}>
                            {inlineCitations.map((citation) => (
                              <a
                                key={`${citation.sectionId}-${citation.pageStart}`}
                                href={citationOriginalUrl(citation)}
                                target="_blank"
                                rel="noreferrer"
                                className={styles.inlineCitation}
                                title={citation.versionLabel || citation.manualTitle}
                              >
                                {citationLabel(citation)}
                              </a>
                            ))}
                          </span>
                        ) : null}
                      </p>
                    );
                  })}
                </div>
              </>
            ) : (
              <p className={styles.outputCopy}>{copy.resultsEmpty}</p>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}
