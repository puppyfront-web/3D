"use client";

import { useState } from "react";
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
} from "lucide-react";
import { mockCompanyAnalysis } from "@/lib/mock-data";

export default function CompanyAnalysisPage() {
  const params = useParams();
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [analysis, setAnalysis] = useState(mockCompanyAnalysis);

  const handleEdit = (field: string, value: string) => {
    setEditingField(field);
    setEditValue(value);
  };

  const handleSave = (field: string) => {
    setAnalysis((prev) => ({ ...prev, [field]: editValue }));
    setEditingField(null);
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
        <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
          <Sparkles className="h-4 w-4" />
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
    </div>
  );
}
