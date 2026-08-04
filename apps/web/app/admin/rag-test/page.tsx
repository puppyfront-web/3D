"use client";

import Link from "next/link";
import { useState } from "react";
import { Search, Loader2, ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { searchKnowledge, type RAGSearchHit } from "@/lib/api";

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

export default function RagTestPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [hits, setHits] = useState<RAGSearchHit[]>([]);
  const [meta, setMeta] = useState<{ total: number; latencyMs: number; retrievalType: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runSearch() {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    const res = await searchKnowledge(q, { topK: 8 });
    if (res.success && res.data) {
      setHits(res.data.results ?? []);
      setMeta({
        total: res.data.total,
        latencyMs: res.data.latencyMs ?? (res.data as { latency_ms?: number }).latency_ms ?? 0,
        retrievalType: res.data.retrievalType ?? (res.data as { retrieval_type?: string }).retrieval_type ?? "hybrid",
      });
    } else {
      setHits([]);
      setMeta(null);
      setError(res.message ?? "检索失败");
    }
    setLoading(false);
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
            验证资料入库后的混合检索效果（与问答助手使用同一检索链路）。若配置了 FastGPT，可在系统设置切换检索后端。
          </p>
        </div>

        <Card>
          <CardContent className="p-4 flex flex-col sm:flex-row gap-3">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="输入测试问题，例如：智汇云有哪些核心能力？"
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
            />
            <Button onClick={runSearch} disabled={loading || !query.trim()} className="shrink-0">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "检索"}
            </Button>
          </CardContent>
        </Card>

        {error ? <p className="text-sm text-error">{error}</p> : null}

        {meta ? (
          <div className="flex gap-2 text-xs text-on-surface-variant">
            <Badge variant="outline">命中 {meta.total}</Badge>
            <Badge variant="outline">{meta.retrievalType}</Badge>
            <Badge variant="outline">{meta.latencyMs} ms</Badge>
          </div>
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
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-sm text-on-surface">{title}</span>
                    <div className="flex gap-2 items-center">
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
