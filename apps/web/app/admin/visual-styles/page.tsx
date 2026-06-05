"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { Plus, Edit3, Trash2, Palette, Eye } from "lucide-react";
import { mockVisualStyles } from "@/lib/mock-data";

export default function VisualStylesPage() {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">视觉风格库</h1>
          <p className="text-sm text-gray-500 mt-1">管理视觉风格预设和参数配置</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
              <Plus className="h-4 w-4" /> 新建风格
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建视觉风格</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>风格名称</Label>
                  <Input placeholder="输入风格名称" />
                </div>
                <div className="space-y-2">
                  <Label>分类</Label>
                  <Input placeholder="输入分类" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea rows={3} placeholder="描述风格特点..." />
              </div>
              <div className="space-y-2">
                <Label>主色调</Label>
                <div className="flex gap-2">
                  <Input type="color" className="w-12 h-9 p-1" defaultValue="#1E3A5F" />
                  <Input placeholder="#1E3A5F" className="flex-1" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>强调色</Label>
                <div className="flex gap-2">
                  <Input type="color" className="w-12 h-9 p-1" defaultValue="#00D4FF" />
                  <Input placeholder="#00D4FF" className="flex-1" />
                </div>
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]">创建风格</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {mockVisualStyles.map((style) => (
          <Card key={style.id} className="border-gray-200 hover:shadow-sm transition-shadow group">
            <CardContent className="p-0">
              {/* Preview */}
              <div
                className="h-32 rounded-t-lg flex items-center justify-center relative"
                style={{
                  background: `linear-gradient(135deg, ${style.parameters.primaryColor}, ${style.parameters.accentColor})`,
                }}
              >
                <Palette className="h-8 w-8 text-white/60" />
                <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Button variant="secondary" size="sm" className="h-6 w-6 p-0"><Eye className="h-3 w-3" /></Button>
                  <Button variant="secondary" size="sm" className="h-6 w-6 p-0"><Edit3 className="h-3 w-3" /></Button>
                </div>
              </div>
              {/* Info */}
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-[#1A1A2E]">{style.name}</h3>
                  <Badge className={`text-xs ${style.isActive ? "bg-green-50 text-[#10B981]" : "bg-gray-100 text-gray-500"}`}>
                    {style.isActive ? "启用" : "停用"}
                  </Badge>
                </div>
                <p className="text-xs text-gray-500 mb-3">{style.description}</p>
                <div className="flex items-center justify-between">
                  <Badge variant="secondary" className="text-xs">{style.category}</Badge>
                  <div className="flex gap-1">
                    <div className="w-4 h-4 rounded-full border border-gray-200" style={{ backgroundColor: style.parameters.primaryColor }} />
                    <div className="w-4 h-4 rounded-full border border-gray-200" style={{ backgroundColor: style.parameters.accentColor }} />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
