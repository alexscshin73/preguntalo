"use client";

import styles from "./manuals-shell.module.css";

import {
  ChangeEvent,
  DragEvent,
  KeyboardEvent,
  MouseEvent as ReactMouseEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { apiUrl } from "../../lib/api";
import { uiText } from "../i18n/ui-text";
import { useUiLanguage } from "../ui-language";

type ManualApiItem = {
  id: string;
  title: string;
  category: string;
  tags: string[];
  updatedAt?: string;
  updated_at?: string;
  defaultLanguage?: string;
  default_language?: string;
  latestVersion?: string;
  latest_version?: string;
};

type ManualItem = {
  id: string;
  title: string;
  category: string;
  tags: string[];
  updatedAt: string;
  defaultLanguage: string;
  latestVersion: string;
};

type ManualVersionItem = {
  id: string;
  manualId: string;
  versionLabel: string;
  sourceLanguage: string;
  originalFilename: string;
  sizeBytes: number;
  uploadedAt: string;
  status: string;
  ingestionJobId: string;
  indexedAt?: string | null;
  latestJobStatus?: string | null;
  latestJobDetail?: string | null;
  latestJobUpdatedAt?: string | null;
  tags: string[];
};

type TreeNode = {
  id: string;
  name: string;
  type: "folder" | "file";
  parentId: string | null;
  updatedAtColumn: string;
  sizeColumn: string;
  typeColumn: string;
  processColumn: string;
  manual?: ManualItem;
  version?: ManualVersionItem;
};

type UploadResponse = {
  versionId: string;
};

type ReindexResponse = {
  ingestionJobId: string;
  status: string;
  detail: string;
  pageCount: number;
  sectionCount: number;
  chunkCount: number;
  tags: string[];
};

type UpdateVersionResponse = {
  id: string;
  manualId: string;
  versionLabel: string;
  sourceLanguage: string;
  originalFilename: string;
  sizeBytes: number;
  uploadedAt: string;
  status: string;
  ingestionJobId: string;
  indexedAt?: string | null;
  latestJobStatus?: string | null;
  latestJobDetail?: string | null;
  latestJobUpdatedAt?: string | null;
  tags: string[];
};

type DeleteVersionResponse = {
  id: string;
  manualId: string;
  deleted: boolean;
};

type PreviewResponse = {
  totalPages?: number;
  mimeType?: string;
  status?: string;
};

type ContextMenuState = {
  x: number;
  y: number;
  node: TreeNode;
};

type PreviewTagHintState = {
  text: string;
  x: number;
  y: number;
};

const DEFAULT_MANUAL_ID = "man_citygolf";
const DEFAULT_README_ID = "seed_readme_md";
const DEFAULT_README_SIZE_BYTES = 12 * 1024;
const MAX_PREVIEW_TAGS = 5;
const COMPACT_TAG_DISPLAY_MAP: Record<string, string> = {
  iniciodesesion: "inicio de sesion",
  pantallaprincipal: "pantalla principal",
  gestionclientes: "gestion clientes",
  cajaliquidacion: "caja liquidacion",
  cambiodeturno: "cambio de turno",
};

function slugifyManualCode(value: string) {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return slug || `manual-${Date.now()}`;
}

function normalizeManual(item: ManualApiItem): ManualItem {
  return {
    id: item.id,
    title:
      item.id === DEFAULT_MANUAL_ID && item.title.trim().toLowerCase() === "citygolf"
        ? "Citygolf"
        : item.title,
    category: item.category,
    tags: item.tags ?? [],
    updatedAt: item.updatedAt ?? item.updated_at ?? "",
    defaultLanguage: item.defaultLanguage ?? item.default_language ?? "en",
    latestVersion: item.latestVersion ?? item.latest_version ?? "-",
  };
}

function fileExtension(filename: string) {
  const extension = filename.split(".").pop();
  return extension ? extension.toLowerCase() : "-";
}

function stripExtension(filename: string) {
  return filename.replace(/\.[^.]+$/, "");
}

function expandCompactTagPart(value: string) {
  return COMPACT_TAG_DISPLAY_MAP[value.toLowerCase()] ?? value.toLowerCase();
}

function formatVersionTagForDisplay(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }

  if (trimmed.includes("/")) {
    return trimmed;
  }

  const koreanFirst = trimmed.match(/^([가-힣]+)([a-záéíóúñü].*)$/i);
  if (koreanFirst) {
    return `${koreanFirst[1]} / ${expandCompactTagPart(koreanFirst[2])}`;
  }

  const latinFirst = trimmed.match(/^([a-záéíóúñü_]+)([가-힣].*)$/i);
  if (latinFirst) {
    return `${latinFirst[2]} / ${expandCompactTagPart(latinFirst[1].replaceAll("_", ""))}`;
  }

  return trimmed;
}

function localizeVersionTagForDisplay(value: string, sourceLanguage: string) {
  const formatted = formatVersionTagForDisplay(value);
  if (!formatted.includes("/")) {
    return formatted;
  }

  const [left, right] = formatted.split("/").map((part) => part.trim());
  return sourceLanguage === "es" ? right || left : left || right;
}

function buildDisplayTagSlots(tags: string[], sourceLanguage: string) {
  const seen = new Set<string>();
  const seenCompactKeys: string[] = [];
  const deduped = tags
    .map((tag) => localizeVersionTagForDisplay(tag, sourceLanguage))
    .map((tag) => tag.trim())
    .filter((tag) => {
      if (!tag) {
        return false;
      }

      const key = tag.toLowerCase().replace(/\s+/g, "");
      if (seen.has(key)) {
        return false;
      }

      if (seenCompactKeys.some((existing) => key.includes(existing) || existing.includes(key))) {
        return false;
      }

      seen.add(key);
      seenCompactKeys.push(key);
      return true;
    })
    .slice(0, MAX_PREVIEW_TAGS);

  return padTagSlots(deduped);
}

function versionHasIndexedTags(version: ManualVersionItem | null) {
  if (!version) {
    return false;
  }

  return Boolean(version.indexedAt) || version.status === "indexed" || version.latestJobStatus === "completed";
}

function padTagSlots(tags: string[]) {
  return Array.from({ length: MAX_PREVIEW_TAGS }, (_, index) => tags[index] ?? "");
}

function formatDate(value: string) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = String(date.getFullYear());

  return `${day}-${month}-${year}`;
}

function formatBytes(sizeBytes: number) {
  if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) {
    return "-";
  }

  if (sizeBytes < 1024) {
    return `${sizeBytes}b`;
  }

  if (sizeBytes < 1024 * 1024) {
    return `${Math.round(sizeBytes / 1024)}kb`;
  }

  return `${(sizeBytes / (1024 * 1024)).toFixed(1)}mb`;
}

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

function getChildren(nodes: TreeNode[], parentId: string | null) {
  return nodes.filter((node) => node.parentId === parentId);
}

function buildFallbackManual(locale: string): ManualItem {
  return {
    id: DEFAULT_MANUAL_ID,
    title: "Citygolf",
    category: "general",
    tags: [],
    updatedAt: new Date().toISOString(),
    defaultLanguage: locale,
    latestVersion: "README",
  };
}

function buildFallbackVersion(locale: string): ManualVersionItem {
  return {
    id: DEFAULT_README_ID,
    manualId: DEFAULT_MANUAL_ID,
    versionLabel: "README",
    sourceLanguage: locale,
    originalFilename: "README.md",
    sizeBytes: DEFAULT_README_SIZE_BYTES,
    uploadedAt: new Date().toISOString(),
    status: "uploaded",
    ingestionJobId: "",
    tags: [],
  };
}

function prioritizeCitygolf(manualItems: ManualItem[]) {
  return [...manualItems].sort((left, right) => {
    const leftPriority = left.id === DEFAULT_MANUAL_ID ? 0 : 1;
    const rightPriority = right.id === DEFAULT_MANUAL_ID ? 0 : 1;

    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }

    return left.title.localeCompare(right.title);
  });
}

export function ManualsShell() {
  const { locale } = useUiLanguage();
  const t = uiText[locale].manuals;
  const filePickerRef = useRef<HTMLInputElement | null>(null);
  const replacePickerRef = useRef<HTMLInputElement | null>(null);

  const [manuals, setManuals] = useState<ManualItem[]>([]);
  const [versionsByManualId, setVersionsByManualId] = useState<Record<string, ManualVersionItem[]>>({});
  const [selectedId, setSelectedId] = useState<string>("");
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [sourceLanguage, setSourceLanguage] = useState<string>(locale);
  const [previewPage, setPreviewPage] = useState(1);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewTotalPages, setPreviewTotalPages] = useState(0);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadTargetManualId, setUploadTargetManualId] = useState<string | null>(null);
  const [dragOverManualId, setDragOverManualId] = useState<string | null>(null);
  const [reindexingVersionId, setReindexingVersionId] = useState<string | null>(null);
  const [savingVersionTagsId, setSavingVersionTagsId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isLocalOnly, setIsLocalOnly] = useState(false);
  const [editingManualId, setEditingManualId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [editingVersionId, setEditingVersionId] = useState<string | null>(null);
  const [editingVersionManualId, setEditingVersionManualId] = useState<string | null>(null);
  const [editingFilename, setEditingFilename] = useState("");
  const [editableVersionTags, setEditableVersionTags] = useState<string[]>(padTagSlots([]));
  const [lastSavedVersionTags, setLastSavedVersionTags] = useState<string[]>(padTagSlots([]));
  const [hoveredPreviewTag, setHoveredPreviewTag] = useState<PreviewTagHintState | null>(null);
  const [replaceTargetVersion, setReplaceTargetVersion] = useState<ManualVersionItem | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const renameInputRef = useRef<HTMLInputElement | null>(null);
  const renameCommitInFlightRef = useRef(false);

  useEffect(() => {
    setSourceLanguage(locale);
  }, [locale]);

  useEffect(() => {
    void loadTree();
  }, []);

  useEffect(() => {
    if (!editingManualId && !editingVersionId) {
      return;
    }

    renameInputRef.current?.focus();
    renameInputRef.current?.select();
  }, [editingManualId, editingVersionId]);

  useEffect(() => {
    if (!editingManualId && !editingVersionId) {
      return;
    }

    function handlePointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }

      if (renameInputRef.current?.contains(target)) {
        return;
      }

      if (editingManualId) {
        void commitRenameManual();
        return;
      }

      if (editingVersionId) {
        void commitRenameVersion();
      }
    }

    window.addEventListener("pointerdown", handlePointerDown, true);

    return () => {
      window.removeEventListener("pointerdown", handlePointerDown, true);
    };
  }, [editingManualId, editingTitle, editingVersionId, editingFilename]);

  useEffect(() => {
    if (!contextMenu) {
      return;
    }

    function handleClose() {
      setContextMenu(null);
    }

    window.addEventListener("click", handleClose);
    window.addEventListener("scroll", handleClose, true);

    return () => {
      window.removeEventListener("click", handleClose);
      window.removeEventListener("scroll", handleClose, true);
    };
  }, [contextMenu]);

  const nodes = useMemo<TreeNode[]>(() => {
    return manuals.flatMap((manual) => {
      const manualNode: TreeNode = {
        id: manual.id,
        name: manual.title,
        type: "folder",
        parentId: null,
        updatedAtColumn: "",
        sizeColumn: "",
        typeColumn: "",
        processColumn: "",
        manual,
      };

      const versionNodes = (versionsByManualId[manual.id] ?? []).map((version) => ({
        id: version.id,
        name: version.originalFilename,
        type: "file" as const,
        parentId: manual.id,
        updatedAtColumn: formatDate(version.uploadedAt),
        sizeColumn: formatBytes(version.sizeBytes),
        typeColumn: fileExtension(version.originalFilename),
        processColumn: version.status,
        manual,
        version,
      }));

      return [manualNode, ...versionNodes];
    });
  }, [manuals, t.types.folder, versionsByManualId]);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedId) ?? null,
    [nodes, selectedId]
  );

  const selectedManual = selectedNode?.manual ?? null;
  const selectedVersion = selectedNode?.version ?? null;

  useEffect(() => {
    const nextTags = versionHasIndexedTags(selectedVersion)
      ? buildDisplayTagSlots(
          selectedVersion?.tags?.slice(0, MAX_PREVIEW_TAGS) ?? [],
          selectedVersion?.sourceLanguage ?? locale
        )
      : padTagSlots([]);
    setEditableVersionTags(nextTags);
    setLastSavedVersionTags(nextTags);
    setHoveredPreviewTag(null);
  }, [
    locale,
    selectedVersion?.id,
    selectedVersion?.sourceLanguage,
    selectedVersion?.status,
    selectedVersion?.indexedAt,
    selectedVersion?.latestJobStatus,
    selectedVersion?.tags,
  ]);

  useEffect(() => {
    if (!selectedVersion) {
      return;
    }

    const currentTags = editableVersionTags
      .map((tag) => normalizeVersionTag(tag))
      .filter((tag) => tag.length > 0)
      .slice(0, MAX_PREVIEW_TAGS);
    const savedTags = lastSavedVersionTags
      .map((tag) => normalizeVersionTag(tag))
      .filter((tag) => tag.length > 0)
      .slice(0, MAX_PREVIEW_TAGS);

    if (JSON.stringify(currentTags) === JSON.stringify(savedTags)) {
      return;
    }

    const timer = window.setTimeout(() => {
      void persistVersionTags(currentTags);
    }, 500);

    return () => {
      window.clearTimeout(timer);
    };
  }, [editableVersionTags, lastSavedVersionTags, selectedVersion?.id]);

  useEffect(() => {
    setPreviewPage(1);
  }, [selectedVersion?.id]);

  useEffect(() => {
    const version = selectedVersion;
    if (!version) {
      setPreviewLoading(false);
      setPreviewTotalPages(0);
      setPreviewError(null);
      return;
    }

    const { id: versionId, manualId } = version;
    let active = true;

    async function loadPreviewMetadata() {
      setPreviewLoading(true);
      setPreviewError(null);
      try {
        const payload = await requestJson<PreviewResponse>(
          `/api/v1/manuals/${manualId}/versions/${versionId}/preview`
        );

        if (!active) {
          return;
        }

        setPreviewTotalPages(Math.max(1, payload.totalPages ?? 1));
      } catch {
        if (active) {
          setPreviewTotalPages(0);
          setPreviewError(t.preview.error);
          setPreviewLoading(false);
        }
      }
    }

    void loadPreviewMetadata();

    return () => {
      active = false;
    };
  }, [selectedVersion?.id, t.preview.error]);

  useEffect(() => {
    if (!selectedVersion) {
      return;
    }

    setPreviewLoading(true);
    setPreviewError(null);
  }, [selectedVersion?.id, previewPage]);

  async function uploadSeedReadme(manualId: string) {
    const seedContent = `# 📘 Manual RAG Service

이 서비스는 매뉴얼을 업로드하고 RAG 기반으로 학습하여, 사용자의 질문에 대해 정확한 정보를 제공합니다.

## 사용 방법
1. 매뉴얼 파일을 업로드합니다.
2. 시스템이 문서를 자동으로 분석 및 임베딩합니다.
3. 주요 내용이 벡터 DB에 저장됩니다.
4. 학습 완료 후 질문 입력이 가능합니다.
5. 질문을 입력하면 관련 문서 기반으로 답변을 생성합니다.
6. 답변은 업로드한 문서 범위 내에서만 제공됩니다.
7. 근거 기반 응답으로 홀로시네이션을 최소화합니다.
8. 필요 시 Reference(출처)도 함께 확인할 수 있습니다.
-----------------------------------------------
Este servicio permite subir manuales, procesarlos con RAG y responder preguntas con información precisa basada en los documentos.

## Uso
1. Suba el archivo del manual.
2. El sistema analiza y genera embeddings automáticamente.
3. La información se almacena en una base de datos vectorial.
4. Una vez finalizado el proceso, puede realizar preguntas.
5. Ingrese su pregunta en el sistema.
6. La respuesta se genera basada únicamente en el contenido del manual.
7. Se minimiza la alucinación mediante respuestas basadas en evidencia.
8. Puede verificar también las referencias (fuentes) relacionadas.`;
    const formData = new FormData();
    formData.append("version_label", "README");
    formData.append("source_language", locale);
    formData.append(
      "file",
      new File([seedContent], "README.md", { type: "text/markdown" })
    );

    await requestJson<UploadResponse>(`/api/v1/manuals/${manualId}/upload`, {
      method: "POST",
      body: formData,
    });
  }

  async function ensureDefaultManualSeed(
    nextManuals: ManualItem[],
    nextVersions: Record<string, ManualVersionItem[]>
  ) {
    const citygolfManual = nextManuals.find(
      (manual) => manual.id === DEFAULT_MANUAL_ID || manual.title.toLowerCase() === "citygolf"
    );

    if (!citygolfManual) {
      const created = await requestJson<{ id: string }>("/api/v1/manuals", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: "Citygolf",
          manualCode: "citygolf",
          category: "general",
          tags: [],
          defaultLanguage: locale,
        }),
      });

      await uploadSeedReadme(created.id);
      return true;
    }

    const hasReadme = (nextVersions[citygolfManual.id] ?? []).some(
      (version) => version.originalFilename === "README.md"
    );

    if (hasReadme) {
      return false;
    }

    await uploadSeedReadme(citygolfManual.id);
    return true;
  }

  async function loadTree(ensureDefault = true) {
    setLoading(true);
    setError(null);

    try {
      const manualPayload = await requestJson<{ items: ManualApiItem[] }>("/api/v1/manuals");
      const nextManuals = prioritizeCitygolf((manualPayload.items ?? []).map(normalizeManual));
      const versionEntries = await Promise.all(
        nextManuals.map(async (manual) => {
          try {
            const payload = await requestJson<{ items: ManualVersionItem[] }>(
              `/api/v1/manuals/${manual.id}/versions`
            );
            return [manual.id, payload.items ?? []] as const;
          } catch {
            return [manual.id, []] as const;
          }
        })
      );

      const nextVersions = Object.fromEntries(versionEntries) as Record<
        string,
        ManualVersionItem[]
      >;

      if (ensureDefault && (await ensureDefaultManualSeed(nextManuals, nextVersions))) {
        await loadTree(false);
        return;
      }

      setIsLocalOnly(false);
      setManuals(nextManuals);
      setVersionsByManualId(nextVersions);
      setExpandedIds((prev) => {
        const next = new Set(prev);
        const defaultManualId = nextManuals.find((manual) => manual.id === DEFAULT_MANUAL_ID)?.id;
        if (defaultManualId) {
          next.add(defaultManualId);
        } else if (nextManuals[0]) {
          next.add(nextManuals[0].id);
        }
        return [...next];
      });
      setSelectedId((prev) => {
        const knownIds = new Set<string>([
          ...nextManuals.map((manual) => manual.id),
          ...Object.values(nextVersions).flatMap((items) => items.map((item) => item.id)),
        ]);

        if (prev && knownIds.has(prev)) {
          return prev;
        }

        return nextManuals.find((manual) => manual.id === DEFAULT_MANUAL_ID)?.id ?? nextManuals[0]?.id ?? "";
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load manuals");
      setIsLocalOnly(false);
      setManuals([]);
      setVersionsByManualId({});
      setExpandedIds([]);
      setSelectedId("");
    } finally {
      setLoading(false);
    }
  }

  function toggleFolder(id: string) {
    setExpandedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  }

  function applyLocalCreateFolder(title: string) {
    const nextManual: ManualItem = {
      id: `local_manual_${Date.now()}`,
      title,
      category: "general",
      tags: [],
      updatedAt: new Date().toISOString(),
      defaultLanguage: locale,
      latestVersion: "-",
    };

    setIsLocalOnly(true);
    setManuals((prev) => prioritizeCitygolf([...prev, nextManual]));
    setVersionsByManualId((prev) => ({
      ...prev,
      [nextManual.id]: [],
    }));
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.add(DEFAULT_MANUAL_ID);
      next.add(nextManual.id);
      return [...next];
    });
    setSelectedId(nextManual.id);
    setNotice(null);
  }

  function applyLocalRenameFolder(manualId: string, title: string) {
    setIsLocalOnly(true);
    setManuals((prev) =>
      prioritizeCitygolf(
        prev.map((manual) =>
          manual.id === manualId
            ? {
                ...manual,
                title,
                updatedAt: new Date().toISOString(),
              }
            : manual
        )
      )
    );
    setSelectedId(manualId);
    cancelRenameManual();
  }

function applyLocalDeleteFolder(manualId: string) {
  setIsLocalOnly(true);
  setManuals((prev) => prev.filter((manual) => manual.id !== manualId));
    setVersionsByManualId((prev) => {
      const next = { ...prev };
      delete next[manualId];
      return next;
    });
  setExpandedIds((prev) => prev.filter((id) => id !== manualId));
    setSelectedId(DEFAULT_MANUAL_ID);
    setNotice(null);
  }

  async function handleCreateFolder(targetManualId?: string) {
    setContextMenu(null);

    const nextTitle = window.prompt("새 폴더 이름을 입력하세요.");
    const title = nextTitle?.trim() ?? "";

    if (!title) {
      return;
    }

    setError(null);
    setNotice(t.messages.creating);

    try {
      const created = await requestJson<{ id: string }>("/api/v1/manuals", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title,
          manualCode: slugifyManualCode(title),
          category: "general",
          tags: [],
          defaultLanguage: locale,
        }),
      });

      await loadTree();
      setExpandedIds((prev) => {
        const next = new Set(prev);
        next.add(DEFAULT_MANUAL_ID);
        if (targetManualId) {
          next.add(targetManualId);
        }
        return [...next];
      });
      setSelectedId(created.id);
      setNotice(null);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create manual");
    }
  }

  function startRenameManual(manual: ManualItem) {
    setContextMenu(null);
    cancelRenameVersion();
    setEditingManualId(manual.id);
    setEditingTitle(manual.title);
  }

  function startRenameVersion(node: TreeNode) {
    if (!node.version || !node.manual) {
      return;
    }

    setContextMenu(null);
    cancelRenameManual();
    setEditingVersionId(node.version.id);
    setEditingVersionManualId(node.manual.id);
    setEditingFilename(node.version.originalFilename);
  }

  function cancelRenameManual() {
    setEditingManualId(null);
    setEditingTitle("");
  }

  function cancelRenameVersion() {
    setEditingVersionId(null);
    setEditingVersionManualId(null);
    setEditingFilename("");
  }

  async function commitRenameManual() {
    if (!editingManualId || renameCommitInFlightRef.current) {
      return;
    }

    renameCommitInFlightRef.current = true;
    const title = editingTitle.trim();
    if (!title) {
      cancelRenameManual();
      renameCommitInFlightRef.current = false;
      return;
    }

    setError(null);

    try {
      await requestJson(`/api/v1/manuals/${editingManualId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title }),
      });

      await loadTree();
      setSelectedId(editingManualId);
      cancelRenameManual();
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : "Failed to rename folder");
    } finally {
      renameCommitInFlightRef.current = false;
    }
  }

  async function commitRenameVersion() {
    if (!editingVersionId || !editingVersionManualId || renameCommitInFlightRef.current) {
      return;
    }

    renameCommitInFlightRef.current = true;
    const filename = editingFilename.trim();
    if (!filename) {
      cancelRenameVersion();
      renameCommitInFlightRef.current = false;
      return;
    }

    setError(null);
    try {
      await requestJson<UpdateVersionResponse>(
        `/api/v1/manuals/${editingVersionManualId}/versions/${editingVersionId}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            originalFilename: filename,
            tags:
              versionsByManualId[editingVersionManualId]?.find((version) => version.id === editingVersionId)?.tags ?? [],
          }),
        }
      );

      await loadTree(false);
      setSelectedId(editingVersionId);
      cancelRenameVersion();
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : "Failed to rename document");
    } finally {
      renameCommitInFlightRef.current = false;
    }
  }

  async function replaceSelectedVersionFile(version: ManualVersionItem, file: File) {
    setError(null);
    setNotice(null);
    setReindexingVersionId(version.id);

    try {
      const formData = new FormData();
      formData.append("file", file);

      await requestJson<UpdateVersionResponse>(
        `/api/v1/manuals/${version.manualId}/versions/${version.id}/replace`,
        {
          method: "POST",
          body: formData,
        }
      );

      setNotice("파일이 교체되었고 다시 정보화가 필요합니다.");
      await loadTree(false);
      setSelectedId(version.id);
    } catch (replaceError) {
      setError(replaceError instanceof Error ? replaceError.message : "Failed to replace file");
    } finally {
      setReindexingVersionId(null);
      setReplaceTargetVersion(null);
    }
  }

  async function handleDeleteManual(manualId: string) {
    setContextMenu(null);

    if (manualId === DEFAULT_MANUAL_ID) {
      setError("기본 폴더는 삭제할 수 없습니다.");
      return;
    }

    const target = manuals.find((manual) => manual.id === manualId);
    const confirmed = window.confirm(`"${target?.title ?? "선택한 폴더"}"를 삭제할까요?`);

    if (!confirmed) {
      return;
    }

    setError(null);

    try {
      await requestJson(`/api/v1/manuals/${manualId}`, {
        method: "DELETE",
      });

      await loadTree();
      setNotice(null);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete folder");
    }
  }

  function handleTreeContextMenu(event: ReactMouseEvent<HTMLDivElement>, node: TreeNode) {
    event.preventDefault();
    setSelectedId(node.id);
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      node,
    });
  }

  function handleModifyManual(manualId: string) {
    const manual = manuals.find((item) => item.id === manualId);
    if (!manual) {
      return;
    }

    setContextMenu(null);
    startRenameManual(manual);
  }

  function applyLocalVersionRename(manualId: string, versionId: string, filename: string) {
    setIsLocalOnly(true);
    setVersionsByManualId((prev) => {
      const next = { ...prev };
      next[manualId] = (next[manualId] ?? []).map((version) =>
        version.id === versionId
          ? {
              ...version,
              originalFilename: filename,
              versionLabel: stripExtension(filename) || version.versionLabel,
            }
          : version
      );
      return next;
    });
    setSelectedId(versionId);
    setNotice("파일명이 로컬에서 변경되었습니다.");
  }

  function applyLocalDeleteVersion(manualId: string, versionId: string) {
    cancelRenameVersion();
    setIsLocalOnly(true);
    setVersionsByManualId((prev) => {
      const next = { ...prev };
      next[manualId] = (next[manualId] ?? []).filter((version) => version.id !== versionId);
      return next;
    });
    if (selectedId === versionId) {
      setSelectedId(manualId);
    }
    setNotice("파일이 로컬에서 삭제되었습니다.");
  }

  async function handleDeleteVersion(node: TreeNode) {
    if (!node.version || !node.manual) {
      return;
    }

    setContextMenu(null);

    if (isLocalOnly) {
      applyLocalDeleteVersion(node.manual.id, node.version.id);
      return;
    }

    const confirmed = window.confirm(`"${node.version.originalFilename}" 파일을 삭제할까요?`);
    if (!confirmed) {
      return;
    }

    setError(null);
    setNotice(null);

    try {
      await requestJson<DeleteVersionResponse>(
        `/api/v1/manuals/${node.manual.id}/versions/${node.version.id}`,
        {
          method: "DELETE",
        }
      );

      await loadTree(false);
      setSelectedId(node.manual.id);
      setNotice("파일이 삭제되었습니다.");
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete file");
    }
  }

  function handleRenameKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void commitRenameManual();
    }

    if (event.key === "Escape") {
      event.preventDefault();
      cancelRenameManual();
    }
  }

  function handleVersionRenameKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void commitRenameVersion();
    }

    if (event.key === "Escape") {
      event.preventDefault();
      cancelRenameVersion();
    }
  }

  function resolveUploadManualId(targetManualId?: string | null) {
    return targetManualId ?? uploadTargetManualId ?? selectedManual?.id ?? null;
  }

  async function uploadFilesToManual(files: File[], targetManualId?: string | null) {
    const manualId = resolveUploadManualId(targetManualId);

    if (!manualId) {
      setError("업로드할 폴더를 먼저 선택하세요.");
      return;
    }

    if (!files.length) {
      return;
    }

    setError(null);
    setUploading(true);
    setNotice(null);

    try {
      let lastVersionId = "";

      for (const file of files) {
        const formData = new FormData();
        formData.append("version_label", stripExtension(file.name));
        formData.append("source_language", sourceLanguage);
        formData.append("file", file);

        const payload = await requestJson<UploadResponse>(`/api/v1/manuals/${manualId}/upload`, {
          method: "POST",
          body: formData,
        });

        lastVersionId = payload.versionId;
      }

      setNotice(t.messages.uploadSuccess);
      await loadTree(false);
      setExpandedIds((prev) => (prev.includes(manualId) ? prev : [...prev, manualId]));
      setSelectedId(lastVersionId || manualId);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Failed to upload file");
    } finally {
      setUploading(false);
      setUploadTargetManualId(null);
    }
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";

    await uploadFilesToManual(files);
  }

  async function handleReplaceFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file || !replaceTargetVersion) {
      setReplaceTargetVersion(null);
      return;
    }

    await replaceSelectedVersionFile(replaceTargetVersion, file);
  }

  function handleOpenFileDialog(targetManualId?: string | null) {
    const manualId = resolveUploadManualId(targetManualId);
    if (!manualId) {
      setError("업로드할 폴더를 먼저 선택하세요.");
      return;
    }

    setError(null);
    setUploadTargetManualId(manualId);
    filePickerRef.current?.click();
  }

  function handleOpenReplaceFileDialog(version: ManualVersionItem) {
    setContextMenu(null);
    setError(null);
    setReplaceTargetVersion(version);
    replacePickerRef.current?.click();
  }

  function handleFolderDragOver(event: DragEvent<HTMLDivElement>, manualId: string) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    if (dragOverManualId !== manualId) {
      setDragOverManualId(manualId);
    }
  }

  function handleFolderDragLeave(event: DragEvent<HTMLDivElement>, manualId: string) {
    const nextTarget = event.relatedTarget;
    if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
      return;
    }

    if (dragOverManualId === manualId) {
      setDragOverManualId(null);
    }
  }

  async function handleFolderDrop(event: DragEvent<HTMLDivElement>, manualId: string) {
    event.preventDefault();
    setDragOverManualId(null);

    const files = Array.from(event.dataTransfer.files ?? []).filter((file) => file.size >= 0);
    if (!files.length) {
      return;
    }

    setSelectedId(manualId);
    setExpandedIds((prev) => (prev.includes(manualId) ? prev : [...prev, manualId]));
    await uploadFilesToManual(files, manualId);
  }

  async function handleReindexVersion(version: ManualVersionItem) {
    if (!version) {
      return;
    }

    setError(null);
    setNotice(null);
    setReindexingVersionId(version.id);

    try {
      const response = await requestJson<ReindexResponse>(
        `/api/v1/manuals/${version.manualId}/versions/${version.id}/reindex`,
        {
          method: "POST",
        }
      );

      setNotice(
        `${t.messages.reindexQueued} Page ${response.pageCount}, section ${response.sectionCount}, chunk ${response.chunkCount}가 생성되고 임베딩 벡터가 인덱싱되었습니다.`
      );
      const nextTags = buildDisplayTagSlots(
        (response.tags ?? []).slice(0, MAX_PREVIEW_TAGS),
        version.sourceLanguage
      );
      setEditableVersionTags(nextTags);
      setLastSavedVersionTags(nextTags);
      await loadTree(false);
      setSelectedId(version.id);
    } catch (reindexError) {
      setError(reindexError instanceof Error ? reindexError.message : "Failed to reindex file");
    } finally {
      setReindexingVersionId(null);
    }
  }

  function normalizeVersionTag(value: string) {
    return value.trim().replace(/^#+/, "").replace(/\s+/g, " ").slice(0, 32);
  }

  function handleVersionTagChange(index: number, value: string) {
    setEditableVersionTags((current) =>
      current.map((tag, currentIndex) => (currentIndex === index ? value : tag))
    );
  }

  function handleRemoveVersionTag(index: number) {
    setEditableVersionTags((current) => {
      const nextTags = current.map((tag, currentIndex) => (currentIndex === index ? "" : tag));
      void persistVersionTags(nextTags);
      return nextTags;
    });
  }

  async function persistVersionTags(nextTags: string[]) {
    if (!selectedVersion) {
      return;
    }

    const normalizedTags = Array.from(
      new Set(
        nextTags
          .map((tag) => normalizeVersionTag(tag))
          .filter((tag) => tag.length > 0)
      )
    ).slice(0, MAX_PREVIEW_TAGS);

    setSavingVersionTagsId(selectedVersion.id);
    setError(null);

    try {
      await requestJson<UpdateVersionResponse>(
        `/api/v1/manuals/${selectedVersion.manualId}/versions/${selectedVersion.id}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            originalFilename: selectedVersion.originalFilename,
            tags: normalizedTags,
          }),
        }
      );

      const paddedTags = padTagSlots(normalizedTags);
      setEditableVersionTags(paddedTags);
      setLastSavedVersionTags(paddedTags);
      await loadTree(false);
      setSelectedId(selectedVersion.id);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save tags");
    } finally {
      setSavingVersionTagsId(null);
    }
  }

  function showPreviewTagHint(tag: string, event: ReactMouseEvent<HTMLElement>) {
    const text = tag.trim();
    if (!text) {
      setHoveredPreviewTag(null);
      return;
    }

    setHoveredPreviewTag({
      text,
      x: event.clientX + 10,
      y: event.clientY + 18,
    });
  }

  function getProcessTone(version: ManualVersionItem) {
    if (version.status === "indexed" || version.latestJobStatus === "completed" || version.indexedAt) {
      return "ok";
    }

    if (version.status === "failed" || version.latestJobStatus === "failed") {
      return "failed";
    }

    return "ready";
  }

  function getProcessLabel(version: ManualVersionItem) {
    const tone = getProcessTone(version);
    if (tone === "ok") {
      return t.buttons.ok;
    }
    return t.buttons.run;
  }

  function renderTree(parentId: string | null, depth = 0) {
    const items = getChildren(nodes, parentId);

    return items.map((item) => {
      const isFolder = item.type === "folder";
      const isExpanded = expandedIds.includes(item.id);
      const hasChildren = getChildren(nodes, item.id).length > 0;

      return (
        <div key={item.id}>
          <div
            className={`${styles.fmTreeRow} ${selectedId === item.id ? styles.fmTreeRowActive : ""} ${
              isFolder && dragOverManualId === item.id ? styles.fmTreeRowDropTarget : ""
            }`}
            onClick={() => {
              setSelectedId(item.id);
              if (isFolder) {
                toggleFolder(item.id);
              }
            }}
            onDoubleClick={() => {
              if (item.version) {
                if (editingVersionId === item.version.id) {
                  void commitRenameVersion();
                } else {
                  startRenameVersion(item);
                }
                return;
              }

              if (item.manual) {
                if (editingManualId === item.manual.id) {
                  void commitRenameManual();
                } else {
                  startRenameManual(item.manual);
                }
              }
            }}
            onContextMenu={(event) => {
              handleTreeContextMenu(event, item);
            }}
            onDragOver={isFolder ? (event) => handleFolderDragOver(event, item.id) : undefined}
            onDragLeave={isFolder ? (event) => handleFolderDragLeave(event, item.id) : undefined}
            onDrop={isFolder ? (event) => void handleFolderDrop(event, item.id) : undefined}
            title={isFolder ? t.treeHint : item.name}
          >
            <div
              className={styles.fmTreeColName}
              style={{ paddingLeft: `${depth * 18 + 14}px` }}
            >
              <span className={styles.fmFolderExpand}>
                {isFolder ? (isExpanded ? "⊟" : "⊞") : "•"}
              </span>

              {isFolder ? <span className={styles.fmFolderIcon}>📁</span> : null}
              {isFolder && item.manual && editingManualId === item.manual.id ? (
                <input
                  ref={renameInputRef}
                  className={styles.fmFolderInlineInput}
                  value={editingTitle}
                  onChange={(event) => setEditingTitle(event.target.value)}
                  onClick={(event) => event.stopPropagation()}
                  onBlur={() => void commitRenameManual()}
                  onKeyDown={handleRenameKeyDown}
                />
              ) : !isFolder && item.version && editingVersionId === item.version.id ? (
                <input
                  ref={renameInputRef}
                  className={styles.fmFolderInlineInput}
                  value={editingFilename}
                  onChange={(event) => setEditingFilename(event.target.value)}
                  onClick={(event) => event.stopPropagation()}
                  onBlur={() => void commitRenameVersion()}
                  onKeyDown={handleVersionRenameKeyDown}
                />
              ) : (
                <span className={styles.fmFolderName}>{item.name}</span>
              )}
            </div>

            <div className={styles.fmTreeColDate}>{item.updatedAtColumn}</div>
            <div className={styles.fmTreeColSize}>{item.sizeColumn}</div>
            <div className={styles.fmTreeColProcess}>
              {item.version ? (
                <button
                  type="button"
                  className={`${styles.fmProcessBtn} ${
                    getProcessTone(item.version) === "ok"
                      ? styles.fmProcessBtnOk
                      : getProcessTone(item.version) === "failed"
                        ? styles.fmProcessBtnFailed
                        : styles.fmProcessBtnReady
                  }`}
                  disabled={reindexingVersionId === item.version.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    void handleReindexVersion(item.version!);
                  }}
                >
                  {getProcessLabel(item.version)}
                </button>
              ) : null}
            </div>
          </div>

          {isFolder && isExpanded && hasChildren ? renderTree(item.id, depth + 1) : null}
        </div>
      );
    });
  }

  const previewPageCount = selectedVersion ? previewTotalPages : 0;
  const previewPages = useMemo(() => {
    if (!previewPageCount) {
      return [];
    }

    return Array.from({ length: previewPageCount }, (_, index) => index + 1);
  }, [previewPageCount]);

  const previewIframeUrl = selectedVersion
    ? `${apiUrl(
        `/api/v1/manuals/${selectedVersion.manualId}/versions/${selectedVersion.id}/download`
      )}#page=${Math.max(1, previewPage)}&zoom=page-fit&view=FitV&pagemode=none&navpanes=0&toolbar=0&scrollbar=0`
    : "";

  return (
    <main className={`${styles.shell} ${styles.shellCobalt}`}>
      <div className={styles.frame}>
        <section className={styles.workspaceWindow}>
          <div className={styles.windowBody}>
            {error ? <div className={`${styles.fmStatusBox} ${styles.fmStatusError}`}>{error}</div> : null}
            {notice ? <div className={`${styles.fmStatusBox} ${styles.fmStatusNotice}`}>{notice}</div> : null}

            <div className={styles.fmLayout}>
              <section className={styles.fmLeftPanel}>
                <div className={styles.fmPanelHead}>
                  <div>
                    <h2 className={styles.fmPanelTitle}>{t.leftTitle}</h2>
                    {t.leftDescription ? (
                      <p className={styles.fmPanelDesc}>{t.leftDescription}</p>
                    ) : null}
                  </div>
                </div>

                <input
                  ref={filePickerRef}
                  className={styles.fmHiddenFile}
                  type="file"
                  multiple
                  onChange={(event) => void handleFileChange(event)}
                />
                <input
                  ref={replacePickerRef}
                  className={styles.fmHiddenFile}
                  type="file"
                  onChange={(event) => void handleReplaceFileChange(event)}
                />

                <div className={`${styles.fmCard} ${styles.fmExplorerCard}`}>
                  <div className={styles.fmExplorerHeader}>
                    <div className={styles.fmExplorerColName}>{t.columns.name}</div>
                    <div className={styles.fmExplorerColDate}>{t.columns.updatedAt}</div>
                    <div className={styles.fmExplorerColSize}>{t.columns.size}</div>
                    <div className={styles.fmExplorerColProcess}>{t.columns.process}</div>
                  </div>

                  <div className={styles.fmExplorerBox}>
                    {loading ? (
                      <div className={styles.emptyState}>{t.messages.loading}</div>
                    ) : nodes.length > 0 ? (
                      renderTree(null)
                    ) : (
                      <div className={styles.emptyState}>{t.empty.noManualSelected}</div>
                    )}
                  </div>
                </div>
              </section>

              <section className={styles.fmMiddlePanel}>
                <div className={styles.fmPreviewCard}>
                  <div className={styles.fmPreviewHead}>
                    <strong>{t.preview.title}</strong>
                  </div>
                  <div className={styles.fmPreviewLayout}>
                    <div className={styles.fmPreviewThumbs}>
                      {previewPages.map((page) => (
                        <button
                          key={page}
                          type="button"
                          className={`${styles.fmThumb} ${
                            previewPage === page ? styles.fmThumbActive : ""
                          }`}
                          title={`${t.preview.page} ${page}`}
                          onClick={() => setPreviewPage(page)}
                        >
                          <span className={styles.fmThumbLabel}>{`Page ${page}`}</span>
                        </button>
                      ))}
                    </div>
                    <div className={styles.fmPreviewMain}>
                      <div className={styles.fmPreviewPage}>
                        <div className={styles.fmPreviewPageInner}>
                          {selectedVersion ? (
                            <>
                              <iframe
                                key={previewIframeUrl}
                                className={styles.fmPreviewIframe}
                                src={previewIframeUrl}
                                title={`Preview ${selectedVersion.originalFilename} page ${previewPage}`}
                                loading="lazy"
                                onLoad={() => setPreviewLoading(false)}
                                onError={() => {
                                  setPreviewLoading(false);
                                  setPreviewError(t.preview.error);
                                }}
                              />
                              {previewLoading ? (
                                <div className={styles.fmPreviewOverlay}>{t.preview.loading}</div>
                              ) : null}
                              {previewError ? (
                                <div className={styles.fmPreviewError}>{previewError}</div>
                              ) : null}
                            </>
                          ) : (
                            <p>파일을 선택하면 미리보기가 표시됩니다.</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  {selectedVersion ? (
                    <div className={styles.fmPreviewTagBox}>
                      <span className={styles.fmPreviewTagLabel}>{t.fields.tags}</span>
                      <div className={styles.fmPreviewTagScroller}>
                        {editableVersionTags.map((tag, index) => (
                          <div
                            key={`${selectedVersion.id}-tag-${index}`}
                            className={styles.fmPreviewTagChip}
                            onMouseEnter={(event) => showPreviewTagHint(tag, event)}
                            onMouseMove={(event) => showPreviewTagHint(tag, event)}
                            onMouseLeave={() => setHoveredPreviewTag(null)}
                          >
                            <input
                              className={styles.fmPreviewTagInput}
                              value={tag}
                              maxLength={32}
                              onChange={(event) => handleVersionTagChange(index, event.target.value)}
                              onMouseMove={(event) => showPreviewTagHint(tag, event)}
                              onBlur={() => {
                                setHoveredPreviewTag(null);
                                void persistVersionTags(editableVersionTags);
                              }}
                              onKeyDown={(event) => {
                                if (event.key === "Enter") {
                                  event.preventDefault();
                                  void persistVersionTags(editableVersionTags);
                                  (event.currentTarget as HTMLInputElement).blur();
                                }
                              }}
                              aria-label={`manual-tag-${index + 1}`}
                            />
                            {tag.trim() ? (
                              <button
                                type="button"
                                className={styles.fmPreviewTagChipRemove}
                                onClick={() => handleRemoveVersionTag(index)}
                                aria-label={`remove-tag-${index + 1}`}
                              >
                                ×
                              </button>
                            ) : null}
                          </div>
                        ))}
                      </div>
                      {hoveredPreviewTag ? (
                        <div
                          className={styles.fmPreviewTagFloatingHint}
                          style={{ left: hoveredPreviewTag.x, top: hoveredPreviewTag.y }}
                        >
                          {hoveredPreviewTag.text}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </section>
            </div>

            {contextMenu ? (
              <div
                className={`${styles.fmContextMenu} ${
                  locale === "es" ? styles.fmContextMenuEs : styles.fmContextMenuKo
                }`}
                style={{ left: contextMenu.x, top: contextMenu.y }}
                onClick={(event) => event.stopPropagation()}
              >
                {(() => {
                  const node = contextMenu.node;
                  const isFolderNode = node.type === "folder";
                  const isFileNode = node.type === "file";

                  return (
                    <>
                      {isFolderNode ? (
                        <>
                          <button
                            type="button"
                            className={styles.fmContextMenuItem}
                            onClick={() => {
                              void handleCreateFolder(node.manual?.id);
                            }}
                          >
                            {t.contextMenu.addFolder}
                          </button>
                          <button
                            type="button"
                            className={styles.fmContextMenuItem}
                            onClick={() => {
                              if (node.manual) {
                                handleModifyManual(node.manual.id);
                              }
                            }}
                          >
                            {t.contextMenu.renameFolder}
                          </button>
                          <button
                            type="button"
                            className={styles.fmContextMenuItem}
                            onClick={() => {
                              if (node.manual) {
                                void handleDeleteManual(node.manual.id);
                              }
                            }}
                          >
                            {t.contextMenu.deleteFolder}
                          </button>
                          <button
                            type="button"
                            className={styles.fmContextMenuItem}
                            onClick={() => {
                              if (node.manual) {
                                handleOpenFileDialog(node.manual.id);
                                setContextMenu(null);
                              }
                            }}
                          >
                            {t.contextMenu.addFile}
                          </button>
                        </>
                      ) : null}
                      {isFileNode ? (
                        <>
                          <button
                            type="button"
                            className={styles.fmContextMenuItem}
                            onClick={() => {
                              startRenameVersion(node);
                            }}
                          >
                            {t.contextMenu.renameFile}
                          </button>
                          <button
                            type="button"
                            className={styles.fmContextMenuItem}
                            onClick={() => {
                              if (node.version) {
                                handleOpenReplaceFileDialog(node.version);
                              }
                            }}
                          >
                            {t.contextMenu.replaceFile}
                          </button>
                          <button
                            type="button"
                            className={styles.fmContextMenuItem}
                            onClick={() => {
                              void handleDeleteVersion(node);
                            }}
                          >
                            {t.contextMenu.deleteFile}
                          </button>
                        </>
                      ) : null}
                    </>
                  );
                })()}
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </main>
  );
}
