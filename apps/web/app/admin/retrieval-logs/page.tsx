"use client";

// Retrieval logs admin page (PRD §9.4 / §12).
//
// Read-only list of recent retrieval_log rows so an admin can audit what each
// agent actually retrieved: the raw query, the structured query, the surfaced
// items, the trigger source, and latency. Filterable by trigger source and
// retrieval type. Clicking a row expands the structured query + retrieved
// items JSON for traceability.

import Link from "next/link";
import { Fragment, useCallback, useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, ChevronDown, ChevronRight, Loader2, Clock } from "lucide-react";
import { getRetrievalLogs, type RetrievalLogItem } from "@/lib/api";
import { cn } from "@/lib/utils";

const TRIGGER_LABEL: Record<string, string> = {
  knowledge_search: "知识库检索",
  knowledge_qa: "问答检索",
  case_search: "案例检索",
  hybrid_retriever: "混合检索",
  rag_search_api: "检索测试",
  rag_hit_test: "检索实验室",
  eval_replay: "评测回放",
  retrieval_orchestrator: "检索编排",
};

const TYPE_LABEL: Record<string, string> = {
  hybrid: "混合",
  keyword: "关键词",
  vector: "向量",
  case_structured: "案例结构化",
};

function triggerLabel(t?: string) {
  if (!t) return "—";
  return TRIGGER_LABEL[t] ?? t;
}

function typeLabel(t?: string) {
  if (!t) return "—";
  return TYPE_LABEL[t] ?? t;
}

function fmtTime(ts: string) {
  return new Date(ts).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function RetrievalLogsPage() {
  const [logs, setLogs] = useState<RetrievalLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggeredBy, setTriggeredBy] = useState<string>("all");
  const [retrievalType, setRetrievalType] = useState<string>("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    const res = await getRetrievalLogs({
      triggered_by: triggeredBy !== "all" ? triggeredBy : undefined,
      retrieval_type: retrievalType !== "all" ? retrievalType : undefined,
      limit: 100,
    });
    if (res.success && res.data) setLogs(res.data);
    setLoading(false);
  }, [triggeredBy, retrievalType]);

  useEffect(() => {
    load();
  }, [load]);

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="flex-1 overflow-y-auto bg-surface">
      <div className="max-w-container-max mx-auto px-margin-desktop py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-on-surface flex items-center gap-2">
              <Search className="h-6 w-6 text-primary" />
              检索日志
            </h1>
            <p className="text-sm text-on-surface-variant mt-1">
              每次 RAG 检索的完整可追溯记录（PRD §9.4）：原始查询、结构化查询、检索条目与触发来源。
            </p>
          </div>
          <div className="flex gap-2">
            <Select value={triggeredBy} onValueChange={setTriggeredBy}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="触发来源" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部来源</SelectItem>
                <SelectItem value="rag_hit_test">检索实验室</SelectItem>
                <SelectItem value="eval_replay">评测回放</SelectItem>
                <SelectItem value="knowledge_qa">问答检索</SelectItem>
                <SelectItem value="case_search">案例检索</SelectItem>
                <SelectItem value="hybrid_retriever">混合检索</SelectItem>
                <SelectItem value="retrieval_orchestrator">检索编排</SelectItem>
              </SelectContent>
            </Select>
            <Select value={retrievalType} onValueChange={setRetrievalType}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="检索类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部类型</SelectItem>
                <SelectItem value="hybrid">混合</SelectItem>
                <SelectItem value="keyword">关键词</SelectItem>
                <SelectItem value="vector">向量</SelectItem>
                <SelectItem value="case_structured">案例结构化</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={load} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "刷新"}
            </Button>
          </div>
        </div>

        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>查询</TableHead>
                  <TableHead className="w-28">触发来源</TableHead>
                  <TableHead className="w-24">类型</TableHead>
                  <TableHead className="w-20 text-right">命中</TableHead>
                  <TableHead className="w-24 text-right">耗时</TableHead>
                  <TableHead className="w-36">时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-outline">
                      <Loader2 className="h-5 w-5 animate-spin mx-auto" />
                    </TableCell>
                  </TableRow>
                )}
                {!loading && logs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-outline">
                      暂无检索日志
                    </TableCell>
                  </TableRow>
                )}
                {logs.map((log) => {
                  const isOpen = expanded.has(log.id);
                  const items = log.retrieved_items_json ?? [];
                  return (
                    <Fragment key={log.id}>
                      <TableRow
                        onClick={() => toggle(log.id)}
                        className="cursor-pointer hover:bg-surface-container-low"
                      >
                        <TableCell className="text-outline">
                          {isOpen ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </TableCell>
                        <TableCell className="font-medium text-on-surface max-w-[420px] truncate">
                          {log.query}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{triggerLabel(log.triggered_by)}</Badge>
                        </TableCell>
                        <TableCell className="text-on-surface-variant text-sm">
                          {typeLabel(log.retrieval_type)}
                        </TableCell>
                        <TableCell className="text-right text-on-surface-variant">
                          {log.results_count}
                        </TableCell>
                        <TableCell className="text-right text-on-surface-variant text-sm">
                          <span className="inline-flex items-center justify-end gap-1">
                            <Clock className="h-3 w-3" />
                            {log.latency_ms ?? "—"}ms
                          </span>
                        </TableCell>
                        <TableCell className="text-outline text-sm">
                          {fmtTime(log.created_at)}
                        </TableCell>
                      </TableRow>
                      {isOpen && (
                        <TableRow key={`${log.id}-detail`} className="bg-surface-container-lowest">
                          <TableCell />
                          <TableCell colSpan={6}>
                            <div className="space-y-3 py-2">
                              {log.structured_query_json &&
                                Object.keys(log.structured_query_json).length > 0 && (
                                  <div>
                                    <p className="text-[10px] uppercase font-semibold text-outline mb-1">
                                      结构化查询
                                    </p>
                                    <pre className="text-xs bg-surface-container p-2 rounded overflow-x-auto">
                                      {JSON.stringify(log.structured_query_json, null, 2)}
                                    </pre>
                                  </div>
                                )}
                              <div>
                                <p className="text-[10px] uppercase font-semibold text-outline mb-1">
                                  检索条目 ({items.length})
                                </p>
                                {items.length === 0 ? (
                                  <p className="text-xs text-outline italic">无命中条目</p>
                                ) : (
                                  <ul className="text-xs space-y-1">
                                    {items.slice(0, 10).map((it, i) => (
                                      <li
                                        key={i}
                                        className={cn(
                                          "flex items-center gap-2 text-on-surface-variant",
                                        )}
                                      >
                                        <Badge variant="secondary" className="text-[10px]">
                                          {String(it.source ?? "—")}
                                        </Badge>
                                        {typeof it.score === "number" && (
                                          <span className="text-outline">
                                            {Number(it.score).toFixed(3)}
                                          </span>
                                        )}
                                        <span className="truncate flex-1">
                                          {String(it.title ?? it.content ?? it.id ?? "—").slice(0, 120)}
                                        </span>
                                        {it.document_id ? (
                                          <a
                                            href={`/admin/assets?doc=${it.document_id}`}
                                            className="text-primary text-[10px] shrink-0 hover:underline"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            查看资料
                                          </a>
                                        ) : null}
                                      </li>
                                    ))}
                                    {items.length > 10 && (
                                      <li className="text-outline text-[10px]">
                                        …还有 {items.length - 10} 条
                                      </li>
                                    )}
                                  </ul>
                                )}
                              </div>
                              {log.final_output_id && (
                                <p className="text-[10px] text-outline">
                                  关联输出：{log.final_output_id}
                                </p>
                              )}
                              {(log.conversation_id || log.project_id) && (
                                <div className="flex flex-wrap gap-3 text-xs">
                                  {log.project_id ? (
                                    <Link
                                      href={`/workspace/chat/${log.project_id}`}
                                      className="text-primary hover:underline"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      打开项目问答
                                    </Link>
                                  ) : null}
                                  {log.message_id ? (
                                    <span className="text-outline">
                                      message={String(log.message_id).slice(0, 8)}…
                                    </span>
                                  ) : null}
                                </div>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
