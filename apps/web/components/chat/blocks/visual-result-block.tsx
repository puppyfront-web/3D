"use client";

import { useState } from "react";
import Image from "next/image";
import { Image as ImageIcon, Maximize2, X } from "lucide-react";

interface VisualResultBlockProps {
  data: Record<string, unknown>;
}

/**
 * Renders visual generation results — strategy and images.
 * Prompts are internal implementation details and are NOT shown to users.
 */
export function VisualResultBlock({ data }: VisualResultBlockProps) {
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

  // Strategy
  const strategy = data.visual_strategy
    ? typeof data.visual_strategy === "string"
      ? data.visual_strategy
      : (data.visual_strategy as Record<string, unknown>)?.concept
        ? String((data.visual_strategy as Record<string, unknown>).concept)
        : null
    : data.strategy
      ? String(data.strategy)
      : null;

  // Images — support both single image_url and images array
  const images: { url: string }[] = [];

  // Single image_url from image_generation skill
  if (data.image_url && typeof data.image_url === "string") {
    images.push({ url: data.image_url });
  }

  // images array (from upload / multi-image results)
  if (Array.isArray(data.images)) {
    for (const img of data.images) {
      if (typeof img === "object" && img.url) {
        images.push({ url: String(img.url) });
      }
    }
  }

  // Composition advice
  const advice = data.composition_advice ? String(data.composition_advice) : null;

  return (
    <>
      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-2.5 bg-purple-50 border-b border-gray-100">
          <ImageIcon className="h-4 w-4 text-purple-600" />
          <span className="text-sm font-medium text-purple-800">视觉结果</span>
        </div>

        <div className="p-4 space-y-3">
          {/* Strategy */}
          {strategy && (
            <div>
              <div className="text-xs text-gray-500 mb-1">视觉策略</div>
              <div className="text-sm text-gray-700">{strategy}</div>
            </div>
          )}

          {/* Image Grid */}
          {images.length > 0 && (
            <div>
              <div className="text-xs text-gray-500 mb-1.5">生成图片</div>
              <div className={`grid gap-2 ${images.length === 1 ? "grid-cols-1" : "grid-cols-2"}`}>
                {images.map((img, i) => (
                  <div
                    key={i}
                    className={`relative group rounded-lg bg-gray-100 overflow-hidden cursor-pointer ${
                      images.length === 1 ? "aspect-[4/3]" : "aspect-square"
                    }`}
                    onClick={() => setLightboxUrl(img.url)}
                  >
                    <Image
                      src={img.url}
                      alt={`生成图片 ${i + 1}`}
                      fill
                      unoptimized
                      className="object-cover transition-transform group-hover:scale-[1.02]"
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                      <Maximize2 className="h-6 w-6 text-white opacity-0 group-hover:opacity-80 transition-opacity" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Composition advice */}
          {advice && (
            <div className="text-xs text-gray-500 bg-gray-50 rounded p-2">
              <span className="font-medium">构图建议：</span>{advice}
            </div>
          )}

          {/* No content fallback */}
          {images.length === 0 && !strategy && (
            <div className="text-sm text-gray-500 text-center py-4">
              视觉方案正在生成中，请稍候…
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
          <div
            className="relative h-full max-h-[90vh] w-full max-w-6xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Image
              src={lightboxUrl}
              alt="生成图片大图预览"
              fill
              unoptimized
              className="object-contain rounded-lg"
            />
          </div>
        </div>
      )}
    </>
  );
}
