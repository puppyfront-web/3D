"use client";

import { useState, useRef } from "react";
import { Upload, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface FileUploadButtonProps {
  accept: string;
  onUpload: (file: File) => Promise<{ imported: number; failed: number; errors: string[] }>;
  label?: string;
  dialogTitle?: string;
  dialogDescription?: string;
  loading?: boolean;
  variant?: "default" | "outline";
}

export function FileUploadButton({
  accept,
  onUpload,
  label = "导入",
  dialogTitle = "导入数据",
  dialogDescription,
  variant = "outline",
}: FileUploadButtonProps) {
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ imported: number; failed: number; errors: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setResult(null);
    setError(null);

    try {
      const res = await onUpload(file);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导入失败");
    } finally {
      setUploading(false);
      // Reset file input so same file can be re-selected
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleClose = (isOpen: boolean) => {
    setOpen(isOpen);
    if (!isOpen) {
      setResult(null);
      setError(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogTrigger asChild>
        <Button variant={variant} size="sm" className="gap-1.5">
          <Upload className="h-3.5 w-3.5" />
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          {dialogDescription && (
            <p className="text-sm text-gray-500">{dialogDescription}</p>
          )}

          {/* File input */}
          <div
            className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center cursor-pointer hover:border-[#1E3A5F]/30 hover:bg-[#1E3A5F]/5 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            <input
              ref={fileRef}
              type="file"
              accept={accept}
              onChange={handleFileChange}
              className="hidden"
              disabled={uploading}
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="h-8 w-8 text-[#1E3A5F] animate-spin" />
                <p className="text-sm text-gray-500">正在导入...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload className="h-8 w-8 text-gray-300" />
                <p className="text-sm text-gray-500">点击选择文件或拖拽到此处</p>
                <p className="text-xs text-gray-400">支持格式: {accept}</p>
              </div>
            )}
          </div>

          {/* Result */}
          {result && (
            <div className="rounded-lg border border-gray-200 p-4 space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-[#10B981]" />
                <span className="text-sm font-medium">
                  成功导入 {result.imported} 条
                </span>
                {result.failed > 0 && (
                  <span className="text-sm text-[#EF4444]">
                    {result.failed} 条失败
                  </span>
                )}
              </div>
              {result.errors.length > 0 && (
                <div className="mt-2 space-y-1">
                  {result.errors.map((err, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-xs text-[#EF4444]">
                      <AlertCircle className="h-3 w-3 mt-0.5 shrink-0" />
                      {err}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-sm text-[#EF4444]">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
