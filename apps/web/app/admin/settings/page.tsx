"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Settings, Eye, EyeOff, Loader2, Check, Cpu, Brain, ImageIcon } from "lucide-react";
import { getAppSettings, updateAppSettings } from "@/lib/api";

interface ServiceConfig {
  provider: string;
  apiKey: string;
  baseUrl: string;
  model: string;
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [llm, setLlm] = useState<ServiceConfig>({
    provider: "mock",
    apiKey: "",
    baseUrl: "",
    model: "gpt-4o",
  });
  const [embedding, setEmbedding] = useState<ServiceConfig>({
    provider: "mock",
    apiKey: "",
    baseUrl: "",
    model: "text-embedding-3-small",
  });
  const [image, setImage] = useState<ServiceConfig>({
    provider: "mock",
    apiKey: "",
    baseUrl: "",
    model: "dall-e-3",
  });

  // 卡片专属参数：embedding 维度、image 质量
  const [embeddingDimensions, setEmbeddingDimensions] = useState("1536");
  const [imageQuality, setImageQuality] = useState("high");

  const [showKeys, setShowKeys] = useState({
    llm: false,
    embedding: false,
    image: false,
  });

  const loadSettings = useCallback(async () => {
    setLoading(true);
    const res = await getAppSettings();
    if (res.success && res.data) {
      const d = res.data;
      setLlm({
        provider: d.llm_provider || "mock",
        apiKey: d.llm_api_key || "",
        baseUrl: d.llm_base_url || "",
        model: d.llm_model || "gpt-4o",
      });
      setEmbedding({
        provider: d.embedding_provider || "mock",
        apiKey: d.embedding_api_key || "",
        baseUrl: d.embedding_base_url || "",
        model: d.embedding_model || "text-embedding-3-small",
      });
      setImage({
        provider: d.image_provider || "mock",
        apiKey: d.image_api_key || "",
        baseUrl: d.image_base_url || "",
        model: d.image_model || "dall-e-3",
      });
      setEmbeddingDimensions(d.embedding_dimensions || "1536");
      setImageQuality(d.image_quality || "high");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    const res = await updateAppSettings({
      llm_provider: llm.provider,
      llm_api_key: llm.apiKey,
      llm_base_url: llm.baseUrl,
      llm_model: llm.model,
      embedding_provider: embedding.provider,
      embedding_api_key: embedding.apiKey,
      embedding_base_url: embedding.baseUrl,
      embedding_model: embedding.model,
      image_provider: image.provider,
      image_api_key: image.apiKey,
      image_base_url: image.baseUrl,
      image_model: image.model,
      embedding_dimensions: embeddingDimensions,
      image_quality: imageQuality,
    });
    if (res.success) {
      setSaved(true);
      // Reload to get masked keys
      await loadSettings();
      setTimeout(() => setSaved(false), 3000);
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  const renderServiceCard = (
    title: string,
    icon: React.ReactNode,
    config: ServiceConfig,
    onChange: (c: ServiceConfig) => void,
    keyName: "llm" | "embedding" | "image",
    defaultModels: string[],
    extra?: React.ReactNode,
  ) => (
    <Card className="border-gray-200">
      <CardHeader className="pb-4">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label className="text-xs">服务提供商</Label>
            <Select
              value={config.provider}
              onValueChange={(v) => onChange({ ...config, provider: v })}
            >
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mock">Mock（本地测试）</SelectItem>
                <SelectItem value="openai">OpenAI / 兼容服务</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-xs">模型</Label>
            <Input
              className="h-9"
              placeholder={defaultModels[0]}
              value={config.model}
              onChange={(e) => onChange({ ...config, model: e.target.value })}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label className="text-xs">API Key</Label>
          <div className="relative">
            <Input
              className="h-9 pr-10"
              type={showKeys[keyName] ? "text" : "password"}
              placeholder="sk-..."
              value={config.apiKey}
              onChange={(e) => onChange({ ...config, apiKey: e.target.value })}
            />
            <button
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              onClick={() =>
                setShowKeys((prev) => ({ ...prev, [keyName]: !prev[keyName] }))
              }
            >
              {showKeys[keyName] ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          <Label className="text-xs">Base URL（可选，用于兼容服务）</Label>
          <Input
            className="h-9"
            placeholder="https://api.openai.com/v1"
            value={config.baseUrl}
            onChange={(e) => onChange({ ...config, baseUrl: e.target.value })}
          />
        </div>
        {extra}
      </CardContent>
    </Card>
  );

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">系统设置</h1>
          <p className="text-sm text-gray-500 mt-1">
            配置 AI 服务提供商和模型参数，保存后即时生效
          </p>
        </div>
        <Settings className="h-5 w-5 text-gray-400" />
      </div>

      <div className="space-y-6">
        {renderServiceCard(
          "LLM 大语言模型",
          <Brain className="h-4 w-4 text-[#1E3A5F]" />,
          llm,
          setLlm,
          "llm",
          ["gpt-4o", "gpt-4o-mini", "deepseek-chat"],
        )}

        {renderServiceCard(
          "Embedding 向量模型",
          <Cpu className="h-4 w-4 text-[#3B82F6]" />,
          embedding,
          setEmbedding,
          "embedding",
          ["text-embedding-3-small", "text-embedding-3-large"],
          <div className="space-y-2">
            <Label className="text-xs">向量维度</Label>
            <Input
              className="h-9"
              type="number"
              placeholder="1536"
              value={embeddingDimensions}
              onChange={(e) => setEmbeddingDimensions(e.target.value)}
            />
          </div>,
        )}

        {renderServiceCard(
          "Image 图片生成",
          <ImageIcon className="h-4 w-4 text-[#EC4899]" />,
          image,
          setImage,
          "image",
          ["dall-e-3", "flux-schnell", "cogview-4"],
          <div className="space-y-2">
            <Label className="text-xs">图片质量</Label>
            <Select
              value={imageQuality}
              onValueChange={(v) => setImageQuality(v)}
            >
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="high">高</SelectItem>
                <SelectItem value="standard">标准</SelectItem>
                <SelectItem value="low">低</SelectItem>
              </SelectContent>
            </Select>
          </div>,
        )}
      </div>

      <div className="mt-6 flex items-center gap-3">
        <Button
          className="bg-[#1E3A5F] hover:bg-[#2D5A8E] min-w-[120px]"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" /> 保存中...
            </>
          ) : saved ? (
            <>
              <Check className="h-4 w-4 mr-2" /> 已保存
            </>
          ) : (
            "保存设置"
          )}
        </Button>
        <span className="text-xs text-gray-400">保存后即时生效，无需重启服务</span>
      </div>
    </div>
  );
}
