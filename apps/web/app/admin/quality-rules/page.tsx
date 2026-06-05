"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Plus,
  Edit3,
  Trash2,
  ShieldCheck,
  ToggleLeft,
  ToggleRight,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { mockQualityRules } from "@/lib/mock-data";

export default function QualityRulesPage() {
  const [expanded, setExpanded] = useState<string[]>([mockQualityRules[0].id]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    );
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">质量标准管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理方案质量评估标准和评分规则</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
              <Plus className="h-4 w-4" /> 新建标准
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建质量标准</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>标准名称</Label>
                  <Input placeholder="输入标准名称" />
                </div>
                <div className="space-y-2">
                  <Label>分类</Label>
                  <Input placeholder="输入分类" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea rows={3} placeholder="描述质量标准..." />
              </div>
              <div className="space-y-2">
                <Label>通过分数线</Label>
                <Input type="number" placeholder="80" />
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]">创建标准</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-4">
        {mockQualityRules.map((rule) => {
          const totalWeight = rule.criteria.reduce((acc, c) => acc + c.weight, 0);
          return (
            <Card key={rule.id} className="border-gray-200">
              <CardHeader
                className="pb-3 cursor-pointer"
                onClick={() => toggleExpand(rule.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {expanded.includes(rule.id) ? (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    )}
                    <ShieldCheck className="h-5 w-5 text-[#1E3A5F]" />
                    <div>
                      <CardTitle className="text-sm font-medium">{rule.name}</CardTitle>
                      <p className="text-xs text-gray-500 mt-0.5">{rule.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="secondary" className="text-xs">{rule.category}</Badge>
                    <Badge variant="outline" className="text-xs">
                      通过线 {rule.passingScore}分
                    </Badge>
                    <Badge className={`text-xs ${rule.isActive ? "bg-green-50 text-[#10B981]" : "bg-gray-100 text-gray-500"}`}>
                      {rule.isActive ? "启用" : "停用"}
                    </Badge>
                    <Button variant="ghost" size="sm" className="h-7 gap-1">
                      <Edit3 className="h-3 w-3" /> 编辑
                    </Button>
                  </div>
                </div>
              </CardHeader>
              {expanded.includes(rule.id) && (
                <CardContent className="pt-0">
                  <Separator className="mb-4" />
                  <div className="ml-7">
                    <div className="grid grid-cols-12 gap-3 text-xs font-medium text-gray-500 mb-2 px-3">
                      <div className="col-span-5">评分标准</div>
                      <div className="col-span-2">权重</div>
                      <div className="col-span-4">评分指南</div>
                      <div className="col-span-1 text-right">操作</div>
                    </div>
                    {rule.criteria.map((criteria) => (
                      <div
                        key={criteria.id}
                        className="grid grid-cols-12 gap-3 items-center px-3 py-2 bg-gray-50 rounded-lg mb-1.5"
                      >
                        <div className="col-span-5 text-sm text-[#1A1A2E]">{criteria.description}</div>
                        <div className="col-span-2">
                          <div className="flex items-center gap-2">
                            <Progress value={(criteria.weight / totalWeight) * 100} className="h-1.5 flex-1" />
                            <span className="text-xs text-gray-600 font-medium">{criteria.weight}%</span>
                          </div>
                        </div>
                        <div className="col-span-4 text-xs text-gray-500">{criteria.scoringGuide}</div>
                        <div className="col-span-1 text-right">
                          <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                            <Edit3 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
