"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
  { title: "基本信息", description: "工作区名称与问题描述" },
  { title: "补充说明", description: "可选的背景资料与备注" },
];

const initialData: ProjectWizardData = {
  screen: {
    screenType: "",
    screenSize: "",
    pitch: "",
    resolution: "",
    installEnvironment: "",
    viewingDistance: "",
    mainViewpoint: "",
    notes: "",
  },
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
      router.push(`/workspace/chat/${result.data.id}`);
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
            <h2 className="text-lg font-semibold text-on-surface">基本信息</h2>
            <p className="text-sm text-gray-500">填写工作区名称与问题描述，无需绑定特定企业</p>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2 col-span-2">
                <Label>工作区名称 *</Label>
                <Input
                  value={data.step1.projectName}
                  onChange={(e) =>
                    setData((prev) => ({
                      ...prev,
                      step1: { ...prev.step1, projectName: e.target.value },
                    }))
                  }
                  placeholder="例如：产品手册检索、制度问答"
                />
              </div>
              <div className="space-y-2">
                <Label>主题标签（可选）</Label>
                <Input
                  value={data.step1.clientName}
                  onChange={(e) =>
                    setData((prev) => ({
                      ...prev,
                      step1: { ...prev.step1, clientName: e.target.value },
                    }))
                  }
                  placeholder="例如：数字化展示、内部制度"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>所属行业（可选）</Label>
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
                    <SelectItem value="解决方案">解决方案</SelectItem>
                    <SelectItem value="咨询服务">咨询服务</SelectItem>
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
            <h2 className="text-lg font-semibold text-on-surface">补充说明</h2>
            <p className="text-sm text-gray-500">可选的背景资料与参考链接，帮助问答更精准（均非必填）</p>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>参考链接</Label>
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
              <Label>背景说明</Label>
              <Textarea
                value={data.step2.companyDescription}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step2: { ...prev.step2, companyDescription: e.target.value } }))
                }
                rows={4}
                placeholder="补充问题背景、使用场景或已有资料摘要…"
              />
            </div>

            <div className="space-y-2">
              <Label>相关对比对象（可选）</Label>
              <Textarea
                value={data.step2.competitors}
                onChange={(e) =>
                  setData((prev) => ({ ...prev, step2: { ...prev.step2, competitors: e.target.value } }))
                }
                rows={3}
                placeholder="列出需要对比的方案、产品或选项，每行一个…"
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
      </WizardForm>
    </div>
  );
}
