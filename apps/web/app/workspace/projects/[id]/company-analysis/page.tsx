"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  Building2,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Lightbulb,
  Edit3,
  Save,
  Sparkles,
  BarChart3,
  Shield,
  Loader2,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  RotateCw,
  Layers,
  Landmark,
  ChevronDown,
  ChevronRight,
  Cpu,
  Compass,
} from "lucide-react";
import {
  getCompanyAnalysis,
  updateCompanyAnalysis,
  generateCompanyAnalysis,
} from "@/lib/api";
import type { CompanyAnalysis as CompanyAnalysisType, SixViews, TechnologyArchitecture, ProjectBackground } from "@/types";

export default function CompanyAnalysisPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [analysis, setAnalysis] = useState<CompanyAnalysisType | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const loadAnalysis = useCallback(async () => {
    setLoading(true);
    const res = await getCompanyAnalysis(projectId);
    if (res.success && res.data) {
      setAnalysis(res.data);
    }
    setLoading(false);
  }, [projectId]);

  useEffect(() => {
    loadAnalysis();
  }, [loadAnalysis]);

  const handleEdit = (field: string, value: string) => {
    setEditingField(field);
    setEditValue(value);
  };

  const handleSave = async (field: string) => {
    if (!analysis) return;
    const updated = { ...analysis, [field]: editValue };
    const res = await updateCompanyAnalysis(projectId, updated);
    if (res.success && res.data) {
      setAnalysis(res.data);
    } else {
      setAnalysis(updated);
    }
    setEditingField(null);
  };

  const handleRegenerate = async () => {
    if (!analysis?.companyId) return;
    setGenerating(true);
    const res = await generateCompanyAnalysis(analysis.companyId);
    if (res.success && res.data) {
      setAnalysis(res.data);
    }
    setGenerating(false);
  };

  const trendIcon = (trend: string) => {
    if (trend === "up") return <TrendingUp className="h-4 w-4 text-[#10B981]" />;
    if (trend === "down") return <TrendingDown className="h-4 w-4 text-[#EF4444]" />;
    return <Minus className="h-4 w-4 text-gray-400" />;
  };

  const severityColor = (severity: string) => {
    if (severity === "high") return "bg-red-50 text-[#EF4444] border-red-200";
    if (severity === "medium") return "bg-amber-50 text-[#F59E0B] border-amber-200";
    return "bg-green-50 text-[#10B981] border-green-200";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-gray-400 gap-3">
        <Building2 className="h-12 w-12 text-gray-300" />
        <p className="text-sm">暂无企业分析数据</p>
        <Button
          onClick={handleRegenerate}
          disabled={generating}
          className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2"
        >
          {generating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> 生成中...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" /> 生成企业分析
            </>
          )}
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-[#1A1A2E]">企业分析报告</h2>
          <p className="text-sm text-gray-500 mt-1">
            AI生成的企业深度分析 · 更新于 {new Date(analysis.generatedAt).toLocaleString("zh-CN")}
          </p>
        </div>
        <Button
          className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2"
          onClick={handleRegenerate}
          disabled={generating}
        >
          {generating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          重新生成分析
        </Button>
      </div>

      {/* Company Overview */}
      <Card className="mb-6 border-gray-200">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-[#1E3A5F]" />
              <CardTitle className="text-sm font-medium">企业概况</CardTitle>
            </div>
            <Badge variant="secondary" className="bg-blue-50 text-[#1E3A5F]">
              {analysis.industry}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          {editingField === "overview" ? (
            <div className="space-y-2">
              <Textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                rows={5}
                className="text-sm"
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={() => handleSave("overview")} className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-1">
                  <Save className="h-3 w-3" /> 保存
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditingField(null)}>取消</Button>
              </div>
            </div>
          ) : (
            <div className="relative group">
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                {analysis.overview}
              </p>
              <Button
                variant="ghost"
                size="sm"
                className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={() => handleEdit("overview", analysis.overview)}
              >
                <Edit3 className="h-3 w-3" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Business Model */}
        <Card className="border-gray-200">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-[#1E3A5F]" />
              <CardTitle className="text-sm font-medium">商业模式分析</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {editingField === "businessModel" ? (
              <div className="space-y-2">
                <Textarea value={editValue} onChange={(e) => setEditValue(e.target.value)} rows={4} className="text-sm" />
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => handleSave("businessModel")} className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-1">
                    <Save className="h-3 w-3" /> 保存
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setEditingField(null)}>取消</Button>
                </div>
              </div>
            ) : (
              <div className="relative group">
                <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                  {analysis.businessModel}
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => handleEdit("businessModel", analysis.businessModel)}
                >
                  <Edit3 className="h-3 w-3" />
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Financial Highlights */}
        <Card className="border-gray-200">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-[#1E3A5F]" />
              <CardTitle className="text-sm font-medium">关键财务指标</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analysis.financialHighlights.map((item, i) => (
                <div key={i} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    {trendIcon(item.trend)}
                    <span className="text-sm text-gray-600">{item.metric}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-[#1E3A5F]">{item.value}</span>
                    <span className="text-xs text-gray-400">{item.year}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Competitive Analysis */}
      <Card className="mb-6 border-gray-200">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-[#1E3A5F]" />
            <CardTitle className="text-sm font-medium">竞品分析</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500">竞争对手</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500">优势</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500">劣势</th>
                  <th className="text-left py-3 px-4 text-xs font-medium text-gray-500">市场份额</th>
                </tr>
              </thead>
              <tbody>
                {analysis.competitiveAnalysis.map((comp, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-3 px-4 font-medium text-[#1A1A2E]">{comp.competitor}</td>
                    <td className="py-3 px-4 text-gray-600">{comp.strength}</td>
                    <td className="py-3 px-4 text-gray-600">{comp.weakness}</td>
                    <td className="py-3 px-4">
                      <Badge variant="secondary" className="bg-blue-50 text-[#1E3A5F]">
                        {comp.marketShare}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-6">
        {/* Risks */}
        <Card className="border-gray-200">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-[#F59E0B]" />
              <CardTitle className="text-sm font-medium">风险评估</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analysis.risks.map((risk, i) => (
                <div key={i} className={`p-3 rounded-lg border ${severityColor(risk.severity)}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{risk.category}</span>
                    <Badge variant="outline" className={`text-xs ${severityColor(risk.severity)}`}>
                      {risk.severity === "high" ? "高风险" : risk.severity === "medium" ? "中风险" : "低风险"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-600 mb-1">{risk.description}</p>
                  <p className="text-xs text-gray-500">应对措施：{risk.mitigation}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Recommendations */}
        <Card className="border-gray-200">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-[#F59E0B]" />
              <CardTitle className="text-sm font-medium">AI 建议</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analysis.recommendations.map((rec, i) => (
                <div key={i} className="flex gap-3 p-3 bg-amber-50/50 rounded-lg">
                  <div className="w-6 h-6 rounded-full bg-[#F59E0B]/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-xs font-medium text-[#F59E0B]">{i + 1}</span>
                  </div>
                  <p className="text-sm text-gray-600 leading-relaxed">{rec}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Enterprise Six Views ── */}
      {analysis.sixViews && (
        <SixViewsSection data={analysis.sixViews} />
      )}

      {/* ── Technology Architecture ── */}
      {analysis.technologyArch && (
        <TechnologyArchSection data={analysis.technologyArch} />
      )}

      {/* ── Project Background ── */}
      {analysis.projectBackground && (
        <ProjectBackgroundSection data={analysis.projectBackground} />
      )}
    </div>
  );
}

// ────────────────────────────────────────────────
// Sub-components for enriched analysis sections
// ────────────────────────────────────────────────

const SIX_VIEW_CONFIG = [
  { key: "backward_history" as const, label: "向后看·发展历史", icon: RotateCcw, color: "text-purple-600", bg: "bg-purple-50" },
  { key: "forward_planning" as const, label: "向前看·发展规划", icon: RotateCw, color: "text-blue-600", bg: "bg-blue-50" },
  { key: "left_competitors" as const, label: "向左看·竞争对手", icon: ArrowLeft, color: "text-orange-600", bg: "bg-orange-50" },
  { key: "right_industry" as const, label: "向右看·行业情况", icon: ArrowRight, color: "text-teal-600", bg: "bg-teal-50" },
  { key: "upward_policy" as const, label: "向上看·政策背景", icon: ArrowUp, color: "text-emerald-600", bg: "bg-emerald-50" },
  { key: "downward_niche" as const, label: "向下看·生态位", icon: ArrowDown, color: "text-rose-600", bg: "bg-rose-50" },
];

function SixViewsSection({ data }: { data: SixViews }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <Card className="mb-6 border-gray-200">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Compass className="h-5 w-5 text-[#1E3A5F]" />
          <CardTitle className="text-sm font-medium">企业六看</CardTitle>
          <Badge variant="secondary" className="bg-purple-50 text-purple-600 text-xs">
            6 维度分析
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-3">
          {SIX_VIEW_CONFIG.map(({ key, label, icon: Icon, color, bg }) => {
            const dimData = data[key];
            if (!dimData) return null;
            const entries = Object.entries(dimData);
            const isExpanded = expanded === key;
            return (
              <div
                key={key}
                className={`rounded-lg border p-3 cursor-pointer transition-all ${bg} border-gray-100 hover:shadow-sm`}
                onClick={() => setExpanded(isExpanded ? null : key)}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={`h-4 w-4 ${color}`} />
                  <span className="text-xs font-medium text-gray-700">{label}</span>
                  {isExpanded ? (
                    <ChevronDown className="h-3 w-3 text-gray-400 ml-auto" />
                  ) : (
                    <ChevronRight className="h-3 w-3 text-gray-400 ml-auto" />
                  )}
                </div>
                {isExpanded ? (
                  <div className="space-y-1.5 mt-2">
                    {entries.map(([k, v]) => (
                      <div key={k} className="text-xs">
                        <span className="text-gray-500">{formatKey(k)}：</span>
                        <span className="text-gray-700 ml-1">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-500 line-clamp-2">
                    {entries.map(([, v]) => String(v)).join(" · ")}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function TechnologyArchSection({ data }: { data: TechnologyArchitecture }) {
  return (
    <Card className="mb-6 border-gray-200">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-[#1E3A5F]" />
          <CardTitle className="text-sm font-medium">技术一张图</CardTitle>
          <Badge variant="secondary" className="bg-blue-50 text-blue-600 text-xs">
            核心技术架构
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {data.layers.map((layer, i) => {
            const levelColors = {
              top: "bg-blue-600 text-white",
              middle: "bg-blue-400 text-white",
              bottom: "bg-blue-200 text-blue-800",
            };
            const levelLabels = { top: "顶层", middle: "中层", bottom: "底层" };
            return (
              <div key={i} className="flex items-stretch gap-3">
                <div className={`w-20 flex-shrink-0 rounded-lg flex flex-col items-center justify-center text-xs font-medium ${levelColors[layer.level]}`}>
                  <span>{levelLabels[layer.level]}</span>
                  <Layers className="h-4 w-4 mt-1 opacity-70" />
                </div>
                <div className="flex-1 bg-gray-50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-[#1A1A2E]">{layer.name}</span>
                    {layer.metaphor && (
                      <Badge variant="outline" className="text-xs border-blue-200 text-blue-600">
                        {layer.metaphor}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-gray-600">{layer.description}</p>
                </div>
              </div>
            );
          })}
        </div>
        {data.core_technology_summary && (
          <div className="mt-3 p-3 bg-blue-50/50 rounded-lg border border-blue-100">
            <p className="text-xs text-blue-800">
              <span className="font-medium">核心技术总结：</span>
              {data.core_technology_summary}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ProjectBackgroundSection({ data }: { data: ProjectBackground }) {
  const levels = [
    { key: "national_policy" as const, label: "宏观·国家政策", color: "border-red-200 bg-red-50/50" },
    { key: "city_or_industry" as const, label: "中观·城市/行业", color: "border-amber-200 bg-amber-50/50" },
    { key: "project_positioning" as const, label: "微观·项目定位", color: "border-emerald-200 bg-emerald-50/50" },
  ];

  return (
    <Card className="mb-6 border-gray-200">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Landmark className="h-5 w-5 text-[#1E3A5F]" />
          <CardTitle className="text-sm font-medium">项目背景</CardTitle>
          <Badge variant="secondary" className="bg-emerald-50 text-emerald-600 text-xs">
            宏观 → 中观 → 微观
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {levels.map(({ key, label, color }, i) => {
            const levelData = data[key];
            if (!levelData) return null;
            return (
              <div key={key}>
                <div className={`rounded-lg border p-4 ${color}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold text-gray-700">{label}</span>
                    {levelData.title && (
                      <span className="text-xs font-medium text-[#1E3A5F]">— {levelData.title}</span>
                    )}
                  </div>
                  {levelData.content && (
                    <p className="text-xs text-gray-600 leading-relaxed whitespace-pre-wrap">
                      {levelData.content}
                    </p>
                  )}
                </div>
                {i < levels.length - 1 && (
                  <div className="flex justify-center py-1">
                    <ArrowDown className="h-4 w-4 text-gray-300" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function formatKey(key: string): string {
  const map: Record<string, string> = {
    founding: "创始背景",
    origin: "起源",
    core_philosophy: "核心理念",
    strategy: "战略方向",
    product_roadmap: "产品路线",
    market_expansion: "市场拓展",
    benchmark_companies: "对标企业",
    differentiation: "差异化定位",
    trends: "行业趋势",
    market_landscape: "市场格局",
    national_policy: "国家政策",
    local_policy: "地方政策",
    core_advantage: "核心优势",
    irreplaceability: "不可替代性",
  };
  return map[key] || key;
}
