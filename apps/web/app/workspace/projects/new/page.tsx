"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { WizardForm } from "@/components/workspace/wizard-form";
import { createProject } from "@/lib/api";
import type { ProjectWizardData, Priority } from "@/types";

const wizardSteps = [
  { title: "基本信息", description: "项目名称与客户信息" },
  { title: "企业调研", description: "目标企业背景资料" },
  { title: "方案风格", description: "方案撰写风格要求" },
  { title: "视觉要求", description: "视觉素材设计规范" },
  { title: "审核与导出", description: "质量标准与输出格式" },
];

const initialData: ProjectWizardData = {
  step1: {
    projectName: "",
    clientName: "",
    industry: "",
    projectType: "",
    description: "",
    priority: "medium",
    dueDate: "",
  },
  step2: {
    companyWebsite: "",
    companyDescription: "",
    competitors: "",
    targetMarket: "",
    existingMaterials: false,
    materialLinks: "",
  },
  step3: {
    proposalStyle: "professional",
    language: "zh-CN",
    toneOfVoice: "professional",
    keySellingPoints: "",
    requiredSections: [],
    additionalRequirements: "",
  },
  step4: {
    visualStyle: "tech-blue",
    colorScheme: "blue-cyan",
    imageStyle: "realistic",
    brandGuidelines: "",
    numberOfImages: 6,
    resolutions: ["1920x1080"],
  },
  step5: {
    qualityLevel: "standard",
    reviewCriteria: ["completeness", "technical", "business"],
    autoExport: true,
    exportFormats: ["pdf", "docx"],
    notifyEmail: "",
  },
};

export default function NewProjectPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [data, setData] = useState<ProjectWizardData>(initialData);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    const result = await createProject(data);
    if (result.success && result.data) {
      router.push(`/workspace/projects/${result.data.id}`);
    }
    setIsSubmitting(false);
  };

  return (
    <div className="h-screen flex flex-col">
      <WizardForm
        steps={wizardSteps}
        currentStep={currentStep}
        onStepChange={setCurrentStep}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      >
        {currentStep === 0 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-[#1A1A2E]">基本信息</h2>
            <p className="text-sm text-gray-500">填写项目名称、客户信息和基本描述</p>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>项目名称 *</Label>
                <Input
                  value={data.step1.projectName}
                  onChange={(e) =>
                    setData((prev) => ({
                      ...prev,
                      step1: { ...prev.step1, projectName: e.target.value },
                    }))
                  }
                  placeholder="例如：智慧城市数字化展厅方案"
                />
              </div>
              <div className="space-y-2">
                <Label>客户名称 *</Label>
                <Input
                  value={data.step1.clientName}
                  onChange={(e) =>
                    setData((prev) => ({
                      ...prev,
                      step1: { ...prev.step1, clientName: e.target.value },
                    }))
                  }
                  placeholder="例如：深圳市科技创新委员会"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>所属行业 *</Label>
                <Select
                  value={data.step1.industry}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step1: { ...prev.step1, industry: v } }))
                  }
                >
                  <SelectTrigger><SelectValue placeholder="选择行业" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="智慧城市">智慧城市</SelectItem>
                    <SelectItem value="工业制造">工业制造</SelectItem>
                    <SelectItem value="新能源汽车">新能源汽车</SelectItem>
                    <SelectItem value="医疗健康">医疗健康</SelectItem>
                    <SelectItem value="金融科技">金融科技</SelectItem>
                    <SelectItem value="跨境电商">跨境电商</SelectItem>
                    <SelectItem value="教育培训">教育培训</SelectItem>
                    <SelectItem value="能源电力">能源电力</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>项目类型</Label>
                <Select
                  value={data.step1.projectType}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step1: { ...prev.step1, projectType: v } }))
                  }
                >
                  <SelectTrigger><SelectValue placeholder="选择类型" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="3D可视化">3D可视化方案</SelectItem>
                    <SelectItem value="数字化转型">数字化转型方案</SelectItem>
                    <SelectItem value="AI应用">AI应用方案</SelectItem>
                    <SelectItem value="平台建设">平台建设方案</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>优先级</Label>
                <Select
                  value={data.step1.priority}
                  onValueChange={(v) =>
                    setData((prev) => ({
                      ...prev,
                      step1: { ...prev.step1, priority: v as Priority },
                    }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">高优先级</SelectItem>
                    <SelectItem value="medium">中优先级</SelectItem>
                    <SelectItem value="low">低优先级</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>截止日期</Label>
              <Input
                type="date"
                value={data.step1.dueDate}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step1: { ...prev.step1, dueDate: e.target.value } }))
                }
                className="w-64"
              />
            </div>

            <div className="space-y-2">
              <Label>项目描述</Label>
              <Textarea
                value={data.step1.description}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step1: { ...prev.step1, description: e.target.value } }))
                }
                rows={4}
                placeholder="简要描述项目目标和核心需求..."
              />
            </div>
          </div>
        )}

        {currentStep === 1 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-[#1A1A2E]">企业调研</h2>
            <p className="text-sm text-gray-500">提供目标企业的背景资料，帮助AI生成更精准的分析</p>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>企业官网</Label>
                <Input
                  value={data.step2.companyWebsite}
                  onChange={(e) =>
                    setData((prev) => ({ ...prev, step2: { ...prev.step2, companyWebsite: e.target.value } }))
                  }
                  placeholder="https://www.example.com"
                />
              </div>
              <div className="space-y-2">
                <Label>目标市场</Label>
                <Input
                  value={data.step2.targetMarket}
                  onChange={(e) =>
                    setData((prev) => ({ ...prev, step2: { ...prev.step2, targetMarket: e.target.value } }))
                  }
                  placeholder="例如：国内一线城市政务市场"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>企业简介</Label>
              <Textarea
                value={data.step2.companyDescription}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step2: { ...prev.step2, companyDescription: e.target.value } }))
                }
                rows={4}
                placeholder="简要描述目标企业的基本情况..."
              />
            </div>

            <div className="space-y-2">
              <Label>主要竞争对手</Label>
              <Textarea
                value={data.step2.competitors}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step2: { ...prev.step2, competitors: e.target.value } }))
                }
                rows={3}
                placeholder="列出主要竞争对手，每行一个..."
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="existing-materials"
                  checked={data.step2.existingMaterials}
                  onCheckedChange={(checked) =>
                    setData((prev) => ({
                      ...prev,
                      step2: { ...prev.step2, existingMaterials: !!checked },
                    }))
                  }
                />
                <Label htmlFor="existing-materials" className="text-sm">
                  已有参考资料或素材
                </Label>
              </div>
              {data.step2.existingMaterials && (
                <Textarea
                  value={data.step2.materialLinks}
                  onChange={(e) =>
                    setData((prev) => ({ ...prev, step2: { ...prev.step2, materialLinks: e.target.value } }))
                  }
                  rows={3}
                  placeholder="粘贴参考资料链接或说明..."
                />
              )}
            </div>
          </div>
        )}

        {currentStep === 2 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-[#1A1A2E]">方案风格</h2>
            <p className="text-sm text-gray-500">定义方案的撰写风格、语言和核心卖点</p>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>方案风格</Label>
                <Select
                  value={data.step3.proposalStyle}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step3: { ...prev.step3, proposalStyle: v } }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="professional">专业严谨</SelectItem>
                    <SelectItem value="innovative">创新前瞻</SelectItem>
                    <SelectItem value="pragmatic">务实落地</SelectItem>
                    <SelectItem value="storytelling">故事叙述</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>语言</Label>
                <Select
                  value={data.step3.language}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step3: { ...prev.step3, language: v } }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="zh-CN">中文</SelectItem>
                    <SelectItem value="en-US">英文</SelectItem>
                    <SelectItem value="bilingual">中英双语</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>语气基调</Label>
                <Select
                  value={data.step3.toneOfVoice}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step3: { ...prev.step3, toneOfVoice: v } }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="professional">专业正式</SelectItem>
                    <SelectItem value="friendly">友好亲和</SelectItem>
                    <SelectItem value="persuasive">说服力强</SelectItem>
                    <SelectItem value="technical">技术深度</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>核心卖点</Label>
              <Textarea
                value={data.step3.keySellingPoints}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step3: { ...prev.step3, keySellingPoints: e.target.value } }))
                }
                rows={3}
                placeholder="列出方案的核心卖点，每行一个..."
              />
            </div>

            <div className="space-y-3">
              <Label>必需章节</Label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: "overview", label: "项目概述" },
                  { id: "requirements", label: "需求分析" },
                  { id: "technical", label: "技术方案" },
                  { id: "implementation", label: "实施计划" },
                  { id: "budget", label: "投资概算" },
                  { id: "team", label: "团队配置" },
                  { id: "cases", label: "成功案例" },
                  { id: "service", label: "售后服务" },
                ].map((section) => (
                  <div key={section.id} className="flex items-center gap-2">
                    <Checkbox
                      id={section.id}
                      checked={data.step3.requiredSections.includes(section.id)}
                      onCheckedChange={(checked) => {
                        const sections = checked
                          ? [...data.step3.requiredSections, section.id]
                          : data.step3.requiredSections.filter((s) => s !== section.id);
                        setData((prev) => ({ ...prev, step3: { ...prev.step3, requiredSections: sections } }));
                      }}
                    />
                    <Label htmlFor={section.id} className="text-sm font-normal">{section.label}</Label>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>其他要求</Label>
              <Textarea
                value={data.step3.additionalRequirements}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step3: { ...prev.step3, additionalRequirements: e.target.value } }))
                }
                rows={3}
                placeholder="其他特殊要求或注意事项..."
              />
            </div>
          </div>
        )}

        {currentStep === 3 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-[#1A1A2E]">视觉要求</h2>
            <p className="text-sm text-gray-500">定义视觉素材的设计规范和生成要求</p>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>视觉风格</Label>
                <Select
                  value={data.step4.visualStyle}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step4: { ...prev.step4, visualStyle: v } }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="tech-blue">科技蓝风格</SelectItem>
                    <SelectItem value="minimal-business">简约商务风</SelectItem>
                    <SelectItem value="nature-eco">自然生态风</SelectItem>
                    <SelectItem value="cyber-future">未来赛博风</SelectItem>
                    <SelectItem value="warm-medical">温暖医疗风</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>配色方案</Label>
                <Select
                  value={data.step4.colorScheme}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step4: { ...prev.step4, colorScheme: v } }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="blue-cyan">蓝青配色</SelectItem>
                    <SelectItem value="dark-gold">深金配色</SelectItem>
                    <SelectItem value="green-white">绿白配色</SelectItem>
                    <SelectItem value="purple-pink">紫粉配色</SelectItem>
                    <SelectItem value="custom">自定义配色</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>图片风格</Label>
                <Select
                  value={data.step4.imageStyle}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step4: { ...prev.step4, imageStyle: v } }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="realistic">写实渲染</SelectItem>
                    <SelectItem value="concept">概念设计</SelectItem>
                    <SelectItem value="flat">扁平插画</SelectItem>
                    <SelectItem value="3d-cartoon">3D卡通</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>生成数量</Label>
                <Input
                  type="number"
                  value={data.step4.numberOfImages}
                  onChange={(e) =>
                    setData((prev) => ({
                      ...prev,
                      step4: { ...prev.step4, numberOfImages: parseInt(e.target.value) || 1 },
                    }))
                  }
                  min={1}
                  max={20}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>品牌规范说明</Label>
              <Textarea
                value={data.step4.brandGuidelines}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step4: { ...prev.step4, brandGuidelines: e.target.value } }))
                }
                rows={3}
                placeholder="描述品牌视觉规范，如Logo使用规则、字体要求等..."
              />
            </div>

            <div className="space-y-3">
              <Label>输出分辨率</Label>
              <div className="flex gap-4">
                {["1920x1080", "3840x2160", "1080x1920", "1024x1024"].map((res) => (
                  <div key={res} className="flex items-center gap-2">
                    <Checkbox
                      id={`res-${res}`}
                      checked={data.step4.resolutions.includes(res)}
                      onCheckedChange={(checked) => {
                        const resolutions = checked
                          ? [...data.step4.resolutions, res]
                          : data.step4.resolutions.filter((r) => r !== res);
                        setData((prev) => ({ ...prev, step4: { ...prev.step4, resolutions } }));
                      }}
                    />
                    <Label htmlFor={`res-${res}`} className="text-sm font-normal">{res}</Label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {currentStep === 4 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-[#1A1A2E]">审核与导出</h2>
            <p className="text-sm text-gray-500">设置质量审核标准和输出格式</p>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>质量等级</Label>
                <Select
                  value={data.step5.qualityLevel}
                  onValueChange={(v) =>
                    setData((prev) => ({ ...prev, step5: { ...prev.step5, qualityLevel: v } }))
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="basic">基础 — 快速生成</SelectItem>
                    <SelectItem value="standard">标准 — 均衡质量</SelectItem>
                    <SelectItem value="premium">高级 — 最高质量</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>通知邮箱</Label>
                <Input
                  type="email"
                  value={data.step5.notifyEmail}
                  onChange={(e) =>
                    setData((prev) => ({ ...prev, step5: { ...prev.step5, notifyEmail: e.target.value } }))
                  }
                  placeholder="完成时通知此邮箱"
                />
              </div>
            </div>

            <div className="space-y-3">
              <Label>审核维度</Label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: "completeness", label: "内容完整性" },
                  { id: "technical", label: "技术可行性" },
                  { id: "business", label: "商务合规性" },
                  { id: "visual", label: "视觉呈现" },
                  { id: "brand", label: "品牌一致性" },
                  { id: "language", label: "语言质量" },
                ].map((criteria) => (
                  <div key={criteria.id} className="flex items-center gap-2">
                    <Checkbox
                      id={criteria.id}
                      checked={data.step5.reviewCriteria.includes(criteria.id)}
                      onCheckedChange={(checked) => {
                        const updatedCriteria = checked
                          ? [...data.step5.reviewCriteria, criteria.id]
                          : data.step5.reviewCriteria.filter((c) => c !== criteria.id);
                        setData((prev) => ({ ...prev, step5: { ...prev.step5, reviewCriteria: updatedCriteria } }));
                      }}
                    />
                    <Label htmlFor={criteria.id} className="text-sm font-normal">{criteria.label}</Label>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="auto-export"
                checked={data.step5.autoExport}
                onCheckedChange={(checked) =>
                  setData((prev) => ({ ...prev, step5: { ...prev.step5, autoExport: !!checked } }))
                }
              />
              <Label htmlFor="auto-export" className="text-sm">
                审核通过后自动导出
              </Label>
            </div>

            <div className="space-y-3">
              <Label>导出格式</Label>
              <div className="flex gap-4">
                {[
                  { id: "pdf", label: "PDF" },
                  { id: "docx", label: "Word (DOCX)" },
                  { id: "pptx", label: "PPT" },
                  { id: "html", label: "HTML" },
                ].map((format) => (
                  <div key={format.id} className="flex items-center gap-2">
                    <Checkbox
                      id={`fmt-${format.id}`}
                      checked={data.step5.exportFormats.includes(format.id)}
                      onCheckedChange={(checked) => {
                        const formats = checked
                          ? [...data.step5.exportFormats, format.id]
                          : data.step5.exportFormats.filter((f) => f !== format.id);
                        setData((prev) => ({ ...prev, step5: { ...prev.step5, exportFormats: formats } }));
                      }}
                    />
                    <Label htmlFor={`fmt-${format.id}`} className="text-sm font-normal">{format.label}</Label>
                  </div>
                ))}
              </div>
            </div>

            {/* Summary */}
            <Card className="bg-[#1E3A5F]/5 border-[#1E3A5F]/10 mt-6">
              <CardContent className="p-4">
                <h3 className="text-sm font-medium text-[#1E3A5F] mb-3">项目创建摘要</h3>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-600">
                  <div>项目名称：{data.step1.projectName || "未填写"}</div>
                  <div>客户名称：{data.step1.clientName || "未填写"}</div>
                  <div>所属行业：{data.step1.industry || "未选择"}</div>
                  <div>优先级：{data.step1.priority === "high" ? "高" : data.step1.priority === "medium" ? "中" : "低"}</div>
                  <div>方案风格：{data.step3.proposalStyle}</div>
                  <div>视觉风格：{data.step4.visualStyle}</div>
                  <div>质量等级：{data.step5.qualityLevel}</div>
                  <div>导出格式：{data.step5.exportFormats.join(", ").toUpperCase()}</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </WizardForm>
    </div>
  );
}
