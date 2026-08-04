"use client";

// CaseSection — the "精选案例" section. Loads real published cases from the
// backend; falls back to designed placeholder cards (aligned with Stitch
// code_home.html) when the case library is empty, so the marketing landing
// never shows a spinner or "暂无案例" hole.

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCases } from "@/lib/api";
import type { CaseItem } from "@/types";
import { Loader2, ArrowRight, MoreHorizontal, Box } from "lucide-react";

// Tint rotation for cases without a cover image (Material 3 derived).
const FALLBACK_TINTS = [
  "bg-primary-fixed text-primary",
  "bg-secondary-fixed text-secondary",
  "bg-tertiary-fixed text-tertiary",
];

// Designed placeholder cases — mirror Stitch code_home.html "Case Studies".
// Shown when the backend has no published/draft cases yet, so first-time
// visitors always see a finished-looking marketing section.
const PLACEHOLDER_CASES = [
  {
    title: "智能制造集团数字化转型项目",
    desc: "构建 3D 数字化工厂，打通设计-生产-运维全链路，实现生产效率提升35%。",
    industry: "制造业",
  },
  {
    title: "智慧园区整体解决方案",
    desc: "以 3D 可视化为核心，提升园区运营与管理效率。实时监控能耗与安全。",
    industry: "园区运营",
  },
  {
    title: "能源企业可视化运维平台",
    desc: "构建三维可视化运维平台，降低运维成本。精准定位设备故障，缩短修复时间。",
    industry: "能源电力",
  },
];

export function CaseSection() {
  const [cases, setCases] = useState<CaseItem[] | null>(null);

  useEffect(() => {
    // 800ms timeout: if the API hasn't returned, fall back to placeholders
    // so the landing page never blocks on a long-running case query.
    const timer = setTimeout(() => {
      setCases((prev) => (prev === null ? [] : prev));
    }, 800);

    getCases()
      .then((res) => {
        clearTimeout(timer);
        if (res.success && res.data) {
          setCases(
            res.data
              .filter((c) => c.status === "published" || c.status === "draft")
              .slice(0, 3),
          );
        } else {
          setCases([]);
        }
      })
      .catch(() => {
        clearTimeout(timer);
        setCases([]);
      });

    return () => clearTimeout(timer);
  }, []);

  // Render: real cases if any, otherwise designed placeholders.
  const renderCases: CaseItem[] =
    cases && cases.length > 0
      ? cases
      : cases === null
        ? []
        : (PLACEHOLDER_CASES.map((p, i) => ({
            id: `placeholder-${i}`,
            title: p.title,
            client: "",
            industry: p.industry,
            outcome: p.desc,
            highlights: [],
            createdAt: new Date().toISOString(),
            status: "draft" as const,
            referenceImages: [],
          })) as CaseItem[]);

  const showPlaceholders = !cases || cases.length === 0;
  const isLoading = cases === null;

  return (
    <section className="py-24 bg-surface-bright">
      <div className="max-w-container-max mx-auto px-margin-desktop">
        <div className="flex justify-between items-end mb-12">
          <div>
            <h2 className="text-3xl md:text-[32px] font-bold text-on-background tracking-tight">
              精选案例
            </h2>
            <p className="text-on-surface-variant text-sm mt-2">
              行业售前方案实践与参考案例
            </p>
          </div>
          <Link
            href="/admin/cases"
            className="text-primary font-bold flex items-center gap-1 hover:underline"
          >
            查看全部
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {isLoading && renderCases.length === 0 ? (
            <div className="col-span-full flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : (
            renderCases.map((c, i) => {
              const cover = c.referenceImages?.[0]?.url;
              const tint = FALLBACK_TINTS[i % FALLBACK_TINTS.length];
              return (
                <div
                  key={c.id}
                  aria-placeholder={showPlaceholders ? "示例案例" : undefined}
                  className="bg-surface-container-lowest rounded-xl border border-outline-variant overflow-hidden group hover:shadow-xl transition-all"
                >
                  <div className="relative h-48 overflow-hidden">
                    {cover ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={cover}
                        alt={c.title}
                        className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                      />
                    ) : (
                      <div
                        className={`w-full h-full flex items-center justify-center ${tint}`}
                      >
                        <Box className="h-12 w-12 opacity-60" strokeWidth={1.5} />
                      </div>
                    )}
                    <div className="absolute top-4 left-4 bg-primary text-on-primary px-3 py-1 rounded-full text-xs">
                      {c.industry || "通用"}
                    </div>
                  </div>
                  <div className="p-6">
                    <h3 className="text-lg font-semibold mb-2">{c.title}</h3>
                    <p className="text-on-surface-variant text-sm line-clamp-2 mb-4">
                      {c.outcome || c.highlights?.[0] || "—"}
                    </p>
                    <div className="pt-4 border-t border-outline-variant flex justify-between items-center text-outline text-xs">
                      <span>
                        {new Date(c.createdAt).toLocaleDateString("zh-CN")}
                      </span>
                      <MoreHorizontal className="h-4 w-4" />
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </section>
  );
}
