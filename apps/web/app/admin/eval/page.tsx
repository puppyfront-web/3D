"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardCheck, Loader2, Play, Trash2, Download, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  createEvalCase,
  createEvalSet,
  deleteEvalCase,
  evalRunMetrics,
  getEvalRun,
  importEvalSmokeTemplate,
  listEvalCases,
  listEvalRuns,
  listEvalSets,
  runEvalSet,
  type EvalCaseItem,
  type EvalRunItem,
  type EvalSetItem,
} from "@/lib/api";

export default function EvalCenterPage() {
  const [sets, setSets] = useState<EvalSetItem[]>([]);
  const [runs, setRuns] = useState<EvalRunItem[]>([]);
  const [selectedSetId, setSelectedSetId] = useState<string>("");
  const [cases, setCases] = useState<EvalCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [runningId, setRunningId] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [caseQuery, setCaseQuery] = useState("");
  const [caseKeywords, setCaseKeywords] = useState("");
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<EvalRunItem | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const [setsRes, runsRes] = await Promise.all([listEvalSets(), listEvalRuns()]);
    if (setsRes.success && setsRes.data) {
      const items = setsRes.data.items ?? [];
      setSets(items);
      setSelectedSetId((prev) => prev || (items[0]?.id ?? ""));
    }
    if (runsRes.success && runsRes.data) setRuns(runsRes.data);
    setLoading(false);
  }, []);

  const loadCases = useCallback(async (setId: string) => {
    if (!setId) {
      setCases([]);
      return;
    }
    const res = await listEvalCases(setId);
    if (res.success && res.data) setCases(res.data);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (selectedSetId) loadCases(selectedSetId);
  }, [selectedSetId, loadCases]);

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    const res = await createEvalSet({ name });
    if (res.success && res.data) {
      setNewName("");
      setSelectedSetId(res.data.id);
      await refresh();
      await loadCases(res.data.id);
    }
  }

  async function handleImportSmoke() {
    setImporting(true);
    const res = await importEvalSmokeTemplate();
    setImporting(false);
    if (res.success && res.data) {
      setSelectedSetId(res.data.id);
      await refresh();
      await loadCases(res.data.id);
    }
  }

  async function handleRun(setId: string) {
    setRunningId(setId);
    await runEvalSet(setId);
    setRunningId(null);
    await refresh();
  }

  async function handleAddCase() {
    const q = caseQuery.trim();
    if (!selectedSetId || !q) return;
    const keywords = caseKeywords
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean);
    const res = await createEvalCase(selectedSetId, {
      query: q,
      expected_keywords: keywords.length ? keywords : undefined,
    });
    if (res.success) {
      setCaseQuery("");
      setCaseKeywords("");
      await loadCases(selectedSetId);
    }
  }

  async function handleDeleteCase(caseId: string) {
    await deleteEvalCase(caseId);
    if (selectedSetId) await loadCases(selectedSetId);
  }

  async function toggleRunDetail(runId: string) {
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      setRunDetail(null);
      return;
    }
    setExpandedRunId(runId);
    const res = await getEvalRun(runId);
    if (res.success && res.data) setRunDetail(res.data);
  }

  const selectedSet = sets.find((s) => s.id === selectedSetId);

  return (
    <div className="max-w-container-max mx-auto px-margin-desktop py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-on-surface flex items-center gap-2">
          <ClipboardCheck className="h-6 w-6 text-primary" />
          评测中心
        </h1>
        <p className="text-sm text-on-surface-variant mt-1">
          黄金问答集批量回放，验证检索 Hit@k（与线上同一检索链路）
        </p>
      </div>

      <Card>
        <CardContent className="p-4 flex flex-col sm:flex-row gap-3 flex-wrap">
          <Input
            placeholder="新建评测集名称"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="sm:max-w-xs"
          />
          <Button onClick={handleCreate} disabled={!newName.trim()}>
            创建评测集
          </Button>
          <Button variant="outline" onClick={handleImportSmoke} disabled={importing}>
            {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            <span className="ml-1">导入交付冒烟模板</span>
          </Button>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : (
        <>
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-on-surface">评测集</h2>
            {sets.length === 0 ? (
              <p className="text-sm text-on-surface-variant">
                暂无评测集。可创建、导入冒烟模板，或在检索实验室保存用例。
              </p>
            ) : (
              sets.map((s) => (
                <Card
                  key={s.id}
                  className={selectedSetId === s.id ? "ring-2 ring-primary/30" : undefined}
                >
                  <CardContent className="p-4 flex items-center justify-between gap-4 flex-wrap">
                    <button
                      type="button"
                      className="text-left"
                      onClick={() => setSelectedSetId(s.id)}
                    >
                      <p className="font-medium text-on-surface">{s.name}</p>
                      <p className="text-xs text-on-surface-variant">{s.id}</p>
                    </button>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/admin/rag-test?evalSetId=${s.id}`}>Lab</Link>
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleRun(s.id)}
                        disabled={runningId === s.id}
                      >
                        {runningId === s.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                        <span className="ml-1">Run</span>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </section>

          {selectedSet ? (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-on-surface">
                用例 · {selectedSet.name}
              </h2>
              <Card>
                <CardContent className="p-4 flex flex-col sm:flex-row gap-3 flex-wrap">
                  <Input
                    placeholder="问句"
                    value={caseQuery}
                    onChange={(e) => setCaseQuery(e.target.value)}
                    className="sm:flex-1"
                  />
                  <Input
                    placeholder="期望关键词（逗号分隔，可选）"
                    value={caseKeywords}
                    onChange={(e) => setCaseKeywords(e.target.value)}
                    className="sm:flex-1"
                  />
                  <Button onClick={handleAddCase} disabled={!caseQuery.trim()}>
                    添加用例
                  </Button>
                </CardContent>
              </Card>
              {cases.length === 0 ? (
                <p className="text-sm text-on-surface-variant">暂无用例</p>
              ) : (
                cases.map((c) => {
                  const kw =
                    c.expected_keywords ??
                    c.expectedKeywords ??
                    [];
                  return (
                    <Card key={c.id}>
                      <CardContent className="p-4 flex justify-between gap-4">
                        <div className="space-y-1 min-w-0">
                          <p className="text-sm font-medium text-on-surface">{c.query}</p>
                          <div className="flex flex-wrap gap-1">
                            {kw.map((k) => (
                              <Badge key={k} variant="outline">
                                {k}
                              </Badge>
                            ))}
                            <Badge variant="secondary">{c.source}</Badge>
                          </div>
                          {c.notes ? (
                            <p className="text-xs text-on-surface-variant">{c.notes}</p>
                          ) : null}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteCase(c.id)}
                          aria-label="删除用例"
                        >
                          <Trash2 className="h-4 w-4 text-error" />
                        </Button>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </section>
          ) : null}

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-on-surface">最近运行</h2>
            {runs.length === 0 ? (
              <p className="text-sm text-on-surface-variant">尚无运行记录</p>
            ) : (
              runs.map((r) => {
                const metrics = evalRunMetrics(r);
                const open = expandedRunId === r.id;
                const perCase =
                  (open && runDetail?.id === r.id
                    ? runDetail.per_case_results_json ?? runDetail.perCaseResultsJson
                    : null) ?? [];
                return (
                  <Card key={r.id}>
                    <CardContent className="p-4 space-y-2">
                      <button
                        type="button"
                        className="w-full text-left flex items-start gap-2"
                        onClick={() => toggleRunDetail(r.id)}
                      >
                        {open ? (
                          <ChevronDown className="h-4 w-4 mt-0.5 shrink-0" />
                        ) : (
                          <ChevronRight className="h-4 w-4 mt-0.5 shrink-0" />
                        )}
                        <div className="flex-1 space-y-2">
                          <div className="flex flex-wrap gap-2 text-xs">
                            <Badge variant="outline">{r.status}</Badge>
                            {metrics ? (
                              <>
                                <Badge variant="outline">
                                  Hit@k {((metrics.hit_at_k_rate ?? 0) * 100).toFixed(0)}%
                                </Badge>
                                <Badge variant="outline">
                                  {metrics.passed}/{metrics.total} 通过
                                </Badge>
                                {"empty_rate" in metrics && metrics.empty_rate != null ? (
                                  <Badge variant="outline">
                                    空结果 {(Number(metrics.empty_rate) * 100).toFixed(0)}%
                                  </Badge>
                                ) : null}
                              </>
                            ) : null}
                          </div>
                          <p className="text-xs text-on-surface-variant">
                            set={r.set_id ?? r.setId} · {r.created_at ?? r.createdAt}
                          </p>
                        </div>
                      </button>
                      {open && perCase.length > 0 ? (
                        <ul className="text-xs space-y-1 border-t border-outline-variant pt-2 mt-2">
                          {perCase.map((row) => {
                            const cid =
                              (row as { case_id?: string }).case_id ??
                              (row as { caseId?: string }).caseId ??
                              "?";
                            return (
                              <li key={cid} className="flex gap-2 items-center">
                                <Badge variant={row.pass ? "secondary" : "outline"}>
                                  {row.pass ? "PASS" : "FAIL"}
                                </Badge>
                                <span className="text-outline">{row.reason ?? "—"}</span>
                                <span className="text-on-surface-variant truncate">case={cid}</span>
                              </li>
                            );
                          })}
                        </ul>
                      ) : null}
                    </CardContent>
                  </Card>
                );
              })
            )}
          </section>
        </>
      )}
    </div>
  );
}
