"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search, Loader2, ExternalLink, BookmarkPlus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  listEvalSets,
  saveEvalCaseFromLab,
  searchKnowledge,
  type EvalSetItem,
  type RAGSearchHit,
} from "@/lib/api";

function hitKey(hit: RAGSearchHit, i: number) {
  return hit.chunkId || hit.documentId || String(i);
}

function hitField(hit: RAGSearchHit & Record<string, unknown>, ...keys: string[]) {
  for (const k of keys) {
    const v = hit[k];
    if (v !== undefined && v !== null) return v;
  }
  return undefined;
}

function RagTestInner() {
  const searchParams = useSearchParams();
  const evalSetFromUrl = searchParams.get("evalSetId") ?? "";

  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [hits, setHits] = useState<RAGSearchHit[]>([]);
  const [meta, setMeta] = useState<{ total: number; latencyMs: number; retrievalType: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [evalSets, setEvalSets] = useState<EvalSetItem[]>([]);
  const [evalSetId, setEvalSetId] = useState(evalSetFromUrl);
  const [savingRank, setSavingRank] = useState<number | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [contextPreview, setContextPreview] = useState<string | null>(null);
  const [logId, setLogId] = useState<string | null>(null);

  const loadSets = useCallback(async () => {
    const res = await listEvalSets();
    if (res.success && res.data) setEvalSets(res.data.items ?? []);
  }, []);

  useEffect(() => {
    loadSets();
  }, [loadSets]);

  useEffect(() => {
    if (evalSetFromUrl) setEvalSetId(evalSetFromUrl);
  }, [evalSetFromUrl]);

  async function runSearch() {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setSaveMsg(null);
    setContextPreview(null);
    setLogId(null);
    const res = await searchKnowledge(q, { topK: 8, includeContextPreview: true });
    if (res.success && res.data) {
      setHits(res.data.results ?? []);
      setMeta({
        total: res.data.total,
        latencyMs: res.data.latencyMs ?? (res.data as { latency_ms?: number }).latency_ms ?? 0,
        retrievalType: res.data.retrievalType ?? (res.data as { retrieval_type?: string }).retrieval_type ?? "hybrid",
      });
      const raw = res.data as Record<string, unknown>;
      setContextPreview(
        (res.data.contextPreviewText as string | undefined) ??
          (raw.context_preview_text as string | undefined) ??
          null
      );
      setLogId(
        (res.data.logId as string | undefined) ??
          (raw.log_id as string | undefined) ??
          null
      );
    } else {
      setHits([]);
      setMeta(null);
      setError(res.message ?? "检索失败");
    }
    setLoading(false);
  }

  async function saveHit(rank: number) {
    if (!evalSetId.trim()) {
      setSaveMsg("请先在上方选择评测集");
      return;
    }
    const q = query.trim();
    if (!q) return;
    setSavingRank(rank);
    setSaveMsg(null);
    const snapshot = hits.map((h) => ({
      chunk_id: h.chunkId,
      document_id: h.documentId,
      content: h.content,
      score: h.score,
      title: h.title,
    }));
    const res = await saveEvalCaseFromLab({
      set_id: evalSetId,
      query: q,
      pick_rank: rank,
      top_k_snapshot: snapshot,
    });
    setSavingRank(null);
    if (res.success) {
      setSaveMsg(`已保存为评测用例（期望 chunk #${rank + 1}）`);
    } else {
      setSaveMsg(res.message ?? "保存失败");
    }
  }

  return (
    <div className="flex-1 overflow-y-auto bg-surface">
      <div className="max-w-container-max mx-auto px-margin-desktop py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-on-surface flex items-center gap-2">
            <Search className="h-6 w-6 text-primary" />
            检索测试
          </h1>
          <p className="text-sm text-on-surface-variant mt-1">
            验证资料入库后的混合检索效果（与问答助手使用同一检索链路）。命中结果可保存到评测集。
          </p>
        </div>

        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              <select
                className="h-10 rounded-md border border-outline-variant bg-surface px-3 text-sm min-w-[200px]"
                value={evalSetId}
                onChange={(e) => setEvalSetId(e.target.value)}
              >
                <option value="">选择评测集（保存用例）</option>
                {evalSets.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <Link href="/admin/eval" className="text-sm text-primary self-center hover:underline shrink-0">
                管理评测集
              </Link>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="输入测试问题，例如：智汇云有哪些核心能力？"
                onKeyDown={(e) => e.key === "Enter" && runSearch()}
              />
              <Button onClick={runSearch} disabled={loading || !query.trim()} className="shrink-0">
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "检索"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {error ? <p className="text-sm text-error">{error}</p> : null}
        {saveMsg ? <p className="text-sm text-primary">{saveMsg}</p> : null}

        {meta ? (
          <div className="flex gap-2 text-xs text-on-surface-variant flex-wrap items-center">
            <Badge variant="outline">命中 {meta.total}</Badge>
            <Badge variant="outline">{meta.retrievalType}</Badge>
            <Badge variant="outline">{meta.latencyMs} ms</Badge>
            {logId ? (
              <Link href="/admin/retrieval-logs" className="text-primary hover:underline">
                日志 {logId.slice(0, 8)}…
              </Link>
            ) : null}
          </div>
        ) : null}

        {contextPreview ? (
          <Card>
            <CardContent className="p-4 space-y-2">
              <p className="text-sm font-medium text-on-surface">Context Pack 预览</p>
              <pre className="text-xs whitespace-pre-wrap text-on-surface-variant bg-surface-container-low rounded p-3 max-h-64 overflow-y-auto">
                {contextPreview}
              </pre>
            </CardContent>
          </Card>
        ) : null}

        <div className="space-y-3">
          {hits.map((raw, i) => {
            const hit = raw as RAGSearchHit & Record<string, unknown>;
            const content = String(hitField(hit, "content") ?? "");
            const title = String(hitField(hit, "title") ?? "文档片段");
            const score = Number(hitField(hit, "score") ?? 0);
            const source = String(hitField(hit, "source") ?? "chunk");
            const documentId = String(hitField(hit, "documentId", "document_id") ?? "");
            return (
              <Card key={hitKey(raw, i)}>
                <CardContent className="p-4 space-y-2">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="font-medium text-sm text-on-surface">{title}</span>
                    <div className="flex gap-2 items-center flex-wrap">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={savingRank === i || !evalSetId}
                        onClick={() => saveHit(i)}
                      >
                        {savingRank === i ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <BookmarkPlus className="h-3 w-3" />
                        )}
                        <span className="ml-1">存为用例</span>
                      </Button>
                      {documentId ? (
                        <Link
                          href={`/admin/assets?doc=${documentId}`}
                          className="text-xs text-primary hover:underline inline-flex items-center gap-0.5"
                        >
                          资料详情
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      ) : null}
                      <Badge variant="secondary">{source}</Badge>
                      <Badge variant="outline">{(score * 100).toFixed(0)}%</Badge>
                    </div>
                  </div>
                  <p className="text-sm text-on-surface-variant whitespace-pre-wrap line-clamp-4">{content}</p>
                </CardContent>
              </Card>
            );
          })}
          {!loading && hits.length === 0 && meta ? (
            <p className="text-sm text-outline text-center py-8">无命中结果，请确认资料已入库。</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function RagTestPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <RagTestInner />
    </Suspense>
  );
}
