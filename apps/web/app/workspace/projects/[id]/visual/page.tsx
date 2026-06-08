"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Image,
  Settings2,
  Wand2,
  Download,
  ZoomIn,
  RefreshCw,
  Palette,
  Maximize2,
  Loader2,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { getVisualProjects, generateVisualImage } from "@/lib/api";
import type { VisualProject, VisualImage } from "@/types";

export default function VisualPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [visualProjects, setVisualProjects] = useState<VisualProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("写实科技风");
  const [size, setSize] = useState("1920x1080");
  const [generating, setGenerating] = useState(false);
  const [images, setImages] = useState<VisualImage[]>([]);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadVisualProjects = useCallback(async () => {
    setLoading(true);
    const res = await getVisualProjects(projectId);
    if (res.success && res.data) {
      setVisualProjects(res.data);
      if (res.data.length > 0) {
        setPrompt(res.data[0].prompt);
        setImages(res.data[0].images);
      }
    }
    setLoading(false);
  }, [projectId]);

  useEffect(() => {
    loadVisualProjects();
  }, [loadVisualProjects]);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setGenerating(true);
    setErrorMsg(null);

    // Parse size into width/height
    const [w, h] = size.split("x").map(Number);
    const res = await generateVisualImage(projectId, prompt, style, w, h);
    if (res.success && res.data) {
      // Backend returns { visual_prompt: {...}, image_generation: {...} }
      // We need to extract the image_url from the response
      const data = res.data as unknown as Record<string, unknown>;
      const imgGen = (data.image_generation as Record<string, unknown>) || {};
      const imgOutput = (imgGen.output as Record<string, unknown>) || {};
      const visualOutput = ((data.visual_prompt as Record<string, unknown>)?.output as Record<string, unknown>) || {};
      const imageUrl = imgOutput.image_url as string | undefined;
      const usedPrompt = (visualOutput.positive_prompt as string) || prompt;

      if (imageUrl) {
        const newImage: VisualImage = {
          id: (imgOutput.task_id as string) || `img-${Date.now()}`,
          url: imageUrl,
          prompt: usedPrompt,
          status: "completed",
          createdAt: new Date().toISOString(),
        };
        setImages((prev) => [newImage, ...prev]);
      } else {
        // Image generation failed but visual prompt succeeded
        const genSuccess = imgGen.success as boolean | undefined;
        if (genSuccess === false) {
          setErrorMsg((imgGen.error as string) || "图片生成失败");
        } else {
          setErrorMsg("未获取到图片URL");
        }
      }
    } else {
      setErrorMsg(res.message || "图片生成失败，请稍后重试");
    }
    setGenerating(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-[#1E3A5F]" />
      </div>
    );
  }

  const handleDownload = async (url: string, filename: string) => {
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch {
      // Fallback: open in new tab
      window.open(url, "_blank");
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)]">
      {/* Column 1: Config */}
      <div className="w-72 border-r border-gray-200 bg-white overflow-y-auto">
        <div className="p-4">
          <div className="flex items-center gap-2 mb-4">
            <Settings2 className="h-4 w-4 text-[#1E3A5F]" />
            <h3 className="text-sm font-semibold text-[#1A1A2E]">生成配置</h3>
          </div>

          <div className="space-y-4">
            <div>
              <Label className="text-xs text-gray-500">画面风格</Label>
              <Select value={style} onValueChange={setStyle}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="写实科技风">写实科技风</SelectItem>
                  <SelectItem value="极简商务风">极简商务风</SelectItem>
                  <SelectItem value="未来赛博风">未来赛博风</SelectItem>
                  <SelectItem value="温暖医疗风">温暖医疗风</SelectItem>
                  <SelectItem value="自然生态风">自然生态风</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-xs text-gray-500">输出尺寸</Label>
              <Select value={size} onValueChange={setSize}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1920x1080">1920 x 1080 (16:9)</SelectItem>
                  <SelectItem value="1280x720">1280 x 720 (16:9)</SelectItem>
                  <SelectItem value="1080x1920">1080 x 1920 (9:16)</SelectItem>
                  <SelectItem value="1024x1024">1024 x 1024 (1:1)</SelectItem>
                  <SelectItem value="3840x2160">3840 x 2160 (4K)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-xs text-gray-500">色彩方案</Label>
              <div className="grid grid-cols-5 gap-2 mt-2">
                {["#1E3A5F", "#00D4FF", "#2D5A8E", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#1A1A2E", "#F5F7FA"].map(
                  (color) => (
                    <button
                      key={color}
                      className="w-9 h-9 rounded-lg border border-gray-200 hover:scale-110 transition-transform"
                      style={{ backgroundColor: color }}
                    />
                  )
                )}
              </div>
            </div>

            <div>
              <Label className="text-xs text-gray-500">预设模板</Label>
              <div className="space-y-2 mt-2">
                {["科技展厅主视觉", "产品3D展示", "信息图表背景", "封面设计"].map(
                  (tpl) => (
                    <button
                      key={tpl}
                      className="w-full text-left px-3 py-2 text-xs text-gray-600 bg-gray-50 rounded-lg hover:bg-[#1E3A5F]/5 transition-colors"
                    >
                      {tpl}
                    </button>
                  )
                )}
              </div>
            </div>

            <div>
              <Label className="text-xs text-gray-500">历史任务</Label>
              <div className="space-y-1 mt-2">
                {visualProjects.map((vp) => (
                  <div
                    key={vp.id}
                    className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg text-xs"
                  >
                    <span className="text-gray-600 truncate flex-1">{vp.name}</span>
                    <Badge variant="secondary" className="text-xs ml-2">
                      {vp.images.length}张
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Column 2: Prompt Editor */}
      <div className="w-96 border-r border-gray-200 bg-white flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Palette className="h-4 w-4 text-[#1E3A5F]" />
              <h3 className="text-sm font-semibold text-[#1A1A2E]">提示词编辑</h3>
            </div>
            <Button variant="ghost" size="sm" className="gap-1 text-xs">
              <RefreshCw className="h-3 w-3" /> 优化提示词
            </Button>
          </div>
          <Textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={8}
            className="text-sm leading-relaxed"
            placeholder="描述您想要生成的图像..."
          />
          <div className="flex items-center justify-between mt-3">
            <span className="text-xs text-gray-400">{prompt.length} 字符</span>
            <Button
              onClick={handleGenerate}
              disabled={generating}
              className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2"
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> 生成中...
                </>
              ) : (
                <>
                  <Wand2 className="h-4 w-4" /> 生成图像
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Prompt suggestions */}
        <div className="p-4 flex-1 overflow-y-auto">
          <p className="text-xs text-gray-400 mb-2">常用提示词片段</p>
          <div className="space-y-1.5">
            {[
              "photorealistic 3D render, 8K quality",
              "futuristic design with blue cyan lighting",
              "clean minimalist professional layout",
              "data visualization dashboard mockup",
              "architecture 3D model with ambient occlusion",
            ].map((suggestion, i) => (
              <button
                key={i}
                className="w-full text-left px-3 py-2 text-xs text-gray-500 bg-gray-50 rounded-lg hover:bg-[#1E3A5F]/5 transition-colors"
                onClick={() => setPrompt((prev) => prev + ", " + suggestion)}
              >
                + {suggestion}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Column 3: Image Results */}
      <div className="flex-1 bg-gray-50 overflow-y-auto">
        <div className="p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Image className="h-4 w-4 text-[#1E3A5F]" />
              <h3 className="text-sm font-semibold text-[#1A1A2E]">生成结果</h3>
              <Badge variant="secondary" className="text-xs">{images.length} 张</Badge>
            </div>
          </div>

          {images.length === 0 && !generating ? (
            <div className="flex flex-col items-center justify-center h-64 text-gray-400">
              <Image className="h-12 w-12 mb-3 text-gray-300" />
              <p className="text-sm">暂无生成结果</p>
              <p className="text-xs mt-1">请在左侧编辑提示词并点击生成</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              {/* Generating placeholder card */}
              {generating && (
                <Card className="overflow-hidden border-blue-200 border-dashed">
                  <div className="relative aspect-video bg-gradient-to-br from-blue-50 to-white flex items-center justify-center">
                    <div className="text-center">
                      <Loader2 className="h-8 w-8 mx-auto mb-2 text-[#1E3A5F] animate-spin" />
                      <p className="text-xs text-[#1E3A5F]">正在生成图片...</p>
                    </div>
                  </div>
                  <CardContent className="p-3">
                    <p className="text-xs text-gray-400 line-clamp-2">{prompt}</p>
                    <div className="mt-2">
                      <Badge variant="outline" className="text-[#F59E0B] border-amber-200">
                        生成中
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Error message */}
              {errorMsg && (
                <div className="col-span-2 rounded-lg border border-red-200 bg-red-50 p-3 flex items-start gap-2">
                  <span className="text-sm text-red-600 flex-1">{errorMsg}</span>
                  <button onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-red-600">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}

              {images.map((img) => (
                <Card key={img.id} className="overflow-hidden border-gray-200 hover:shadow-md transition-shadow group">
                  <div className="relative aspect-video bg-gray-100 overflow-hidden">
                    {img.url && !img.url.startsWith("/") ? (
                      <img
                        src={img.url}
                        alt="生成图片"
                        className="w-full h-full object-cover transition-transform group-hover:scale-[1.02]"
                      />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-[#1E3A5F] via-[#2D5A8E] to-[#00D4FF] flex items-center justify-center">
                        <div className="text-center text-white">
                          <Image className="h-8 w-8 mx-auto mb-2 opacity-60" />
                          <p className="text-xs opacity-80">无图片</p>
                        </div>
                      </div>
                    )}
                    {img.url && !img.url.startsWith("/") && (
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                        <div className="flex gap-2">
                          <Button
                            variant="secondary"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() => setLightboxUrl(img.url)}
                          >
                            <ZoomIn className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() => handleDownload(img.url, `visual-${img.id}.png`)}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() => setLightboxUrl(img.url)}
                          >
                            <Maximize2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                  <CardContent className="p-3">
                    <p className="text-xs text-gray-500 line-clamp-2">{img.prompt}</p>
                    <div className="flex items-center justify-between mt-2">
                      <Badge
                        variant="outline"
                        className={
                          img.status === "completed"
                            ? "text-[#10B981] border-green-200"
                            : img.status === "failed"
                            ? "text-[#EF4444] border-red-200"
                            : "text-[#F59E0B] border-amber-200"
                        }
                      >
                        {img.status === "completed" ? "已完成" : img.status === "failed" ? "失败" : "生成中"}
                      </Badge>
                      <span className="text-xs text-gray-400">
                        {new Date(img.createdAt).toLocaleString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Lightbox overlay */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setLightboxUrl(null)}
        >
          <button
            className="absolute top-4 right-4 text-white/80 hover:text-white p-2"
            onClick={() => setLightboxUrl(null)}
          >
            <X className="h-6 w-6" />
          </button>
          <img
            src={lightboxUrl}
            alt="Preview"
            className="max-w-full max-h-full object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
