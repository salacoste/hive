import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  FileText,
  Folder,
  Loader2,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

import {
  sessionsApi,
  type SessionFileEntry,
  type SessionFilePreviewResponse,
} from "@/api/sessions";

interface DataExplorerModalProps {
  open: boolean;
  sessionId: string | null;
  onClose: () => void;
}

type TreeNode = {
  name: string;
  path: string;
  type: "file" | "dir";
  entry: SessionFileEntry | null;
  children: Map<string, TreeNode>;
};

type VisibleTreeRow = {
  node: TreeNode;
  depth: number;
  forceExpanded: boolean;
};

function formatBytes(size: number | null): string {
  if (size == null) return "-";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(unixSeconds: number): string {
  if (!unixSeconds || Number.isNaN(unixSeconds)) return "-";
  return new Date(unixSeconds * 1000).toLocaleString();
}

function sortNodes(nodes: TreeNode[]): TreeNode[] {
  return [...nodes].sort((a, b) => {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

function buildTree(entries: SessionFileEntry[]): TreeNode[] {
  const root = new Map<string, TreeNode>();
  const sortedEntries = [...entries].sort((a, b) => a.path.localeCompare(b.path));
  for (const entry of sortedEntries) {
    const parts = entry.path.split("/").filter(Boolean);
    if (parts.length === 0) continue;
    let cursor = root;
    for (let i = 0; i < parts.length; i++) {
      const name = parts[i];
      const isLeaf = i === parts.length - 1;
      const path = parts.slice(0, i + 1).join("/");
      const fallbackType: "dir" | "file" = isLeaf ? entry.type : "dir";
      const existing = cursor.get(name);
      if (existing) {
        if (isLeaf) {
          existing.type = entry.type;
          existing.entry = entry;
        }
        cursor = existing.children;
        continue;
      }
      const created: TreeNode = {
        name,
        path,
        type: fallbackType,
        entry: isLeaf ? entry : null,
        children: new Map<string, TreeNode>(),
      };
      cursor.set(name, created);
      cursor = created.children;
    }
  }
  return sortNodes([...root.values()]);
}

function detectPreviewMode(path: string | null, content: string | null): "json" | "log" | "text" {
  if (!path || !content) return "text";
  const lower = path.toLowerCase();
  if (lower.endsWith(".json")) return "json";
  if (/^\s*[{\[]/.test(content)) {
    try {
      JSON.parse(content);
      return "json";
    } catch {
      // fall through
    }
  }
  if (
    lower.endsWith(".log") ||
    lower.endsWith(".out") ||
    /\b(error|warn|warning|info|debug|trace)\b/i.test(content)
  ) {
    return "log";
  }
  return "text";
}

function renderJsonValueSegment(rawValue: string) {
  const value = rawValue.trim();
  const leading = rawValue.slice(0, rawValue.length - value.length);
  let cls = "text-foreground";
  if (value.startsWith("\"")) cls = "text-emerald-300";
  else if (/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(value)) cls = "text-cyan-300";
  else if (value === "true" || value === "false") cls = "text-amber-300";
  else if (value === "null") cls = "text-violet-300";
  else if (value === "{" || value === "}" || value === "[" || value === "]") cls = "text-muted-foreground";
  return (
    <>
      <span className="text-foreground">{leading}</span>
      <span className={cls}>{value}</span>
    </>
  );
}

function JsonPreview({ content }: { content: string }) {
  let source = content;
  try {
    source = JSON.stringify(JSON.parse(content), null, 2);
  } catch {
    // keep raw content
  }
  const lines = source.split("\n");
  return (
    <pre className="text-xs leading-5 whitespace-pre text-foreground font-mono">
      {lines.map((line, idx) => {
        const keyValueMatch = line.match(/^(\s*)"([^"]+)"(\s*:\s*)(.*?)(,?)$/);
        if (!keyValueMatch) {
          return (
            <div key={idx}>
              {renderJsonValueSegment(line)}
            </div>
          );
        }
        const [, indent, key, separator, valuePart, comma] = keyValueMatch;
        return (
          <div key={idx}>
            <span className="text-foreground">{indent}</span>
            <span className="text-sky-300">"{key}"</span>
            <span className="text-foreground">{separator}</span>
            {renderJsonValueSegment(valuePart)}
            <span className="text-foreground">{comma}</span>
          </div>
        );
      })}
    </pre>
  );
}

function LogPreview({ content }: { content: string }) {
  const lines = content.split("\n");
  return (
    <pre className="text-xs leading-5 whitespace-pre-wrap break-words text-foreground font-mono">
      {lines.map((line, idx) => {
        const level = /\b(ERROR|ERR)\b/i.test(line)
          ? "error"
          : /\b(WARN|WARNING)\b/i.test(line)
            ? "warn"
            : /\b(INFO)\b/i.test(line)
              ? "info"
              : /\b(DEBUG|TRACE)\b/i.test(line)
                ? "debug"
                : "default";
        const lineCls =
          level === "error"
            ? "text-red-300"
            : level === "warn"
              ? "text-amber-300"
              : level === "info"
                ? "text-sky-300"
                : level === "debug"
                  ? "text-muted-foreground"
                  : "text-foreground";
        const tsMatch = line.match(/^(\[[^\]]+\]|\d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}[^\s]*)(\s+)(.*)$/);
        if (!tsMatch) {
          return (
            <div key={idx} className={lineCls}>
              {line}
            </div>
          );
        }
        const [, ts, sep, rest] = tsMatch;
        return (
          <div key={idx} className={lineCls}>
            <span className="text-muted-foreground">{ts}</span>
            <span>{sep}</span>
            <span>{rest}</span>
          </div>
        );
      })}
    </pre>
  );
}

export default function DataExplorerModal({
  open,
  sessionId,
  onClose,
}: DataExplorerModalProps) {
  const [entries, setEntries] = useState<SessionFileEntry[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listRefreshing, setListRefreshing] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [listTruncated, setListTruncated] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [preview, setPreview] = useState<SessionFilePreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [copyDone, setCopyDone] = useState(false);

  const selectedEntry = useMemo(
    () => entries.find((entry) => entry.path === selectedPath) ?? null,
    [entries, selectedPath],
  );

  const rootNodes = useMemo(() => buildTree(entries), [entries]);

  const visibleRows = useMemo(() => {
    const out: VisibleTreeRow[] = [];
    const query = searchQuery.trim().toLowerCase();

    const collectSearch = (node: TreeNode, depth: number): VisibleTreeRow[] => {
      const matchSelf =
        node.name.toLowerCase().includes(query) ||
        node.path.toLowerCase().includes(query);
      if (node.type === "file") {
        return matchSelf ? [{ node, depth, forceExpanded: false }] : [];
      }
      const childRows = sortNodes([...node.children.values()]).flatMap((child) =>
        collectSearch(child, depth + 1),
      );
      if (!matchSelf && childRows.length === 0) return [];
      return [{ node, depth, forceExpanded: true }, ...childRows];
    };

    const collectNormal = (node: TreeNode, depth: number) => {
      out.push({ node, depth, forceExpanded: false });
      if (node.type === "dir" && expandedDirs.has(node.path)) {
        for (const child of sortNodes([...node.children.values()])) {
          collectNormal(child, depth + 1);
        }
      }
    };

    if (query) {
      for (const node of rootNodes) {
        out.push(...collectSearch(node, 0));
      }
      return out;
    }

    for (const node of rootNodes) {
      collectNormal(node, 0);
    }
    return out;
  }, [expandedDirs, rootNodes, searchQuery]);

  const previewMode = useMemo(
    () => detectPreviewMode(selectedEntry?.path ?? null, preview?.content ?? null),
    [preview?.content, selectedEntry?.path],
  );

  const toggleDir = useCallback((path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const handleCopyPreview = useCallback(async () => {
    if (!preview?.content) return;
    try {
      await navigator.clipboard.writeText(preview.content);
      setCopyDone(true);
    } catch {
      setCopyDone(false);
    }
  }, [preview?.content]);

  useEffect(() => {
    if (!copyDone) return;
    const timer = window.setTimeout(() => setCopyDone(false), 1300);
    return () => window.clearTimeout(timer);
  }, [copyDone]);

  const refreshList = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!sessionId) return;
      const silent = opts?.silent === true;
      if (silent) setListRefreshing(true);
      else setListLoading(true);
      setListError(null);
      try {
        const data = await sessionsApi.files(sessionId);
        const sorted = [...(data.entries || [])].sort((a, b) => a.path.localeCompare(b.path));
        setEntries(sorted);
        setListTruncated(Boolean(data.truncated));

        const topLevelDirs = new Set<string>();
        for (const entry of sorted) {
          if (entry.type === "dir" && !entry.path.includes("/")) {
            topLevelDirs.add(entry.path);
          }
        }
        setExpandedDirs((prev) => {
          if (prev.size > 0) return prev;
          return topLevelDirs;
        });

        if (sorted.length === 0) {
          setSelectedPath(null);
          setPreview(null);
          setPreviewError(null);
          return;
        }

        const stillExists = sorted.some((entry) => entry.path === selectedPath);
        const firstFile = sorted.find((entry) => entry.type === "file") ?? null;
        if (!stillExists) {
          setSelectedPath(firstFile?.path ?? sorted[0].path);
          setPreview(null);
          setPreviewError(null);
        }
      } catch (err) {
        setListError(err instanceof Error ? err.message : "Failed to load session files");
      } finally {
        if (silent) setListRefreshing(false);
        else setListLoading(false);
      }
    },
    [selectedPath, sessionId],
  );

  useEffect(() => {
    if (!open || !sessionId) return;
    refreshList().catch(() => {});
  }, [open, refreshList, sessionId]);

  useEffect(() => {
    if (!open) return;
    setExpandedDirs(new Set());
    setSearchQuery("");
    setCopyDone(false);
    setSelectedPath(null);
    setPreview(null);
    setPreviewError(null);
  }, [open, sessionId]);

  useEffect(() => {
    if (!open || !sessionId || !selectedEntry || selectedEntry.type !== "file") return;
    setPreviewLoading(true);
    setPreviewError(null);
    sessionsApi
      .previewFile(sessionId, selectedEntry.path)
      .then((data) => {
        setPreview(data);
      })
      .catch((err) => {
        setPreview(null);
        setPreviewError(err instanceof Error ? err.message : "Failed to load file preview");
      })
      .finally(() => {
        setPreviewLoading(false);
      });
  }, [open, selectedEntry, sessionId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/45 backdrop-blur-[1px] flex items-center justify-center p-4">
      <div
        className="absolute inset-0"
        onClick={onClose}
      />
      <div className="relative w-full max-w-6xl h-[85vh] rounded-xl border border-border/60 bg-card shadow-2xl overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b border-border/60 flex items-center gap-2">
          <Folder className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Session Data Explorer</h3>
          {sessionId && (
            <span className="text-[11px] text-muted-foreground truncate max-w-[320px]">
              {sessionId}
            </span>
          )}
          <button
            onClick={() => refreshList({ silent: true }).catch(() => {})}
            className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted/40"
            disabled={listLoading || listRefreshing || !sessionId}
          >
            <RefreshCw className={`w-3 h-3 ${(listLoading || listRefreshing) ? "animate-spin" : ""}`} />
            Refresh
          </button>
          {sessionId && (
            <a
              href={`/api/sessions/${encodeURIComponent(sessionId)}/export`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted/40"
            >
              <Download className="w-3 h-3" />
              Download .zip
            </a>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted/40"
            title="Close"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex-1 min-h-0 grid grid-cols-[360px_1fr]">
          <div className="border-r border-border/60 min-h-0 flex flex-col">
            <div className="px-3 py-2 border-b border-border/40 text-[11px] text-muted-foreground">
              Files
              {listTruncated ? " (truncated list)" : ""}
            </div>
            <div className="px-2 py-2 border-b border-border/40">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2 top-1/2 -translate-y-1/2" />
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search files..."
                  className="w-full rounded-md border border-border/60 bg-background px-8 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
                />
              </div>
            </div>
            <div className="flex-1 min-h-0 overflow-auto">
              {listLoading ? (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Loading files...
                </div>
              ) : listError ? (
                <div className="p-3 text-xs text-destructive">{listError}</div>
              ) : visibleRows.length === 0 ? (
                <div className="p-3 text-xs text-muted-foreground">
                  {searchQuery.trim() ? "No files match the search query." : "No files yet."}
                </div>
              ) : (
                <div className="py-1">
                  {visibleRows.map(({ node, depth, forceExpanded }) => {
                    const active = node.path === selectedPath;
                    const entry = node.entry;
                    const isDir = node.type === "dir";
                    const expanded = forceExpanded || expandedDirs.has(node.path);
                    const childCount = node.children.size;
                    return (
                      <button
                        key={node.path}
                        onClick={() => {
                          if (isDir) {
                            if (!searchQuery.trim()) toggleDir(node.path);
                            setSelectedPath(node.path);
                            setPreview(null);
                            setPreviewError(null);
                            return;
                          }
                          setSelectedPath(node.path);
                        }}
                        className={`w-full text-left py-1.5 pr-2 text-xs transition-colors ${
                          active
                            ? "bg-primary/10 text-foreground"
                            : "text-foreground hover:bg-muted/30"
                        }`}
                        style={{ paddingLeft: `${12 + depth * 14}px` }}
                      >
                        <div className="flex items-center gap-1.5">
                          {isDir ? (
                            expanded ? (
                              <ChevronDown className="w-3 h-3 text-muted-foreground" />
                            ) : (
                              <ChevronRight className="w-3 h-3 text-muted-foreground" />
                            )
                          ) : (
                            <span className="w-3 h-3" />
                          )}
                          {isDir ? (
                            <Folder className="w-3 h-3 text-muted-foreground" />
                          ) : (
                            <FileText className="w-3 h-3 text-muted-foreground" />
                          )}
                          <span className="truncate flex-1">{node.name}</span>
                          {isDir && (
                            <span className="text-[10px] text-muted-foreground">{childCount}</span>
                          )}
                        </div>
                        <div className="mt-0.5 pl-[18px] text-[10px] text-muted-foreground/80">
                          {isDir
                            ? "Directory"
                            : formatBytes(entry?.size ?? null)}
                          {entry ? ` · ${formatTimestamp(entry.modified)}` : ""}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="min-h-0 flex flex-col">
            <div className="px-3 py-2 border-b border-border/40 flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground truncate flex-1">
                {selectedEntry?.path || "Select a file"}
              </span>
              {sessionId && selectedEntry?.type === "file" && (
                <button
                  onClick={() => {
                    void handleCopyPreview();
                  }}
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted/40"
                  title="Copy preview content"
                  disabled={!preview?.content}
                >
                  {copyDone ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      Copy
                    </>
                  )}
                </button>
              )}
              {sessionId && selectedEntry?.type === "file" && (
                <a
                  href={sessionsApi.fileDownloadUrl(sessionId, selectedEntry.path)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted/40"
                >
                  <Download className="w-3 h-3" />
                  Download
                </a>
              )}
            </div>

            <div className="flex-1 min-h-0 overflow-auto">
              {!selectedEntry ? (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                  Select a file to preview.
                </div>
              ) : selectedEntry.type === "dir" ? (
                <div className="p-4 text-xs text-muted-foreground">
                  This is a directory.
                </div>
              ) : previewLoading ? (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Loading preview...
                </div>
              ) : previewError ? (
                <div className="p-4 text-xs text-destructive">{previewError}</div>
              ) : preview?.binary ? (
                <div className="p-4 text-xs text-muted-foreground">
                  Binary file preview is not available. Use Download.
                </div>
              ) : (
                <div className="p-3">
                  {previewMode === "json" && preview?.content ? (
                    <JsonPreview content={preview.content} />
                  ) : previewMode === "log" && preview?.content ? (
                    <LogPreview content={preview.content} />
                  ) : (
                    <pre className="text-xs leading-5 whitespace-pre-wrap break-words text-foreground font-mono">
                      {preview?.content || ""}
                    </pre>
                  )}
                  {preview?.truncated && (
                    <div className="mt-2 text-[11px] text-muted-foreground">
                      Preview truncated to {preview.preview_limit_bytes.toLocaleString()} bytes.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
