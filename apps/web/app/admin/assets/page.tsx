"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Plus,
  Search,
  Upload,
  Download,
  Trash2,
  Eye,
  MoreHorizontal,
  Package,
  Image,
  FileText,
  Video,
} from "lucide-react";
import { mockAssets } from "@/lib/mock-data";
import type { AssetType } from "@/types";

const typeIcons: Record<AssetType, React.ReactNode> = {
  image: <Image className="h-4 w-4 text-green-500" />,
  video: <Video className="h-4 w-4 text-purple-500" />,
  document: <FileText className="h-4 w-4 text-blue-500" />,
  template: <FileText className="h-4 w-4 text-amber-500" />,
  model: <Package className="h-4 w-4 text-[#00D4FF]" />,
};

export default function AssetsPage() {
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState<string>("all");

  const filtered = mockAssets.filter((a) => {
    const matchesSearch = a.name.toLowerCase().includes(search.toLowerCase());
    const matchesType = filterType === "all" || a.type === filterType;
    return matchesSearch && matchesType;
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-[#1A1A2E]">资产管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理3D模型、图片、视频等素材资源</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button className="bg-[#1E3A5F] hover:bg-[#2D5A8E] gap-2">
              <Upload className="h-4 w-4" /> 上传资产
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>上传新资产</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label>资产名称</Label>
                <Input placeholder="输入资产名称" />
              </div>
              <div className="space-y-2">
                <Label>资产类型</Label>
                <Select>
                  <SelectTrigger><SelectValue placeholder="选择类型" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="image">图片</SelectItem>
                    <SelectItem value="video">视频</SelectItem>
                    <SelectItem value="document">文档</SelectItem>
                    <SelectItem value="template">模板</SelectItem>
                    <SelectItem value="model">3D模型</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>分类</Label>
                <Input placeholder="输入分类" />
              </div>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <Upload className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                <p className="text-sm text-gray-500">拖拽文件到此处或点击上传</p>
                <p className="text-xs text-gray-400 mt-1">支持最大2GB</p>
              </div>
              <div className="space-y-2">
                <Label>标签</Label>
                <Input placeholder="输入标签，逗号分隔" />
              </div>
              <Button className="w-full bg-[#1E3A5F] hover:bg-[#2D5A8E]">上传</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="搜索资产..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex gap-1.5">
          {["all", "image", "video", "document", "template", "model"].map((t) => (
            <Button
              key={t}
              variant={filterType === t ? "default" : "outline"}
              size="sm"
              onClick={() => setFilterType(t)}
              className={filterType === t ? "bg-[#1E3A5F] hover:bg-[#2D5A8E]" : ""}
            >
              {t === "all" ? "全部" : t === "image" ? "图片" : t === "video" ? "视频" : t === "document" ? "文档" : t === "template" ? "模板" : "3D模型"}
            </Button>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card className="border-gray-200">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">资产名称</TableHead>
                <TableHead className="text-xs">类型</TableHead>
                <TableHead className="text-xs">分类</TableHead>
                <TableHead className="text-xs">大小</TableHead>
                <TableHead className="text-xs">上传者</TableHead>
                <TableHead className="text-xs">上传时间</TableHead>
                <TableHead className="text-xs">标签</TableHead>
                <TableHead className="text-xs text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((asset) => (
                <TableRow key={asset.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {typeIcons[asset.type]}
                      <span className="text-sm font-medium text-[#1A1A2E]">{asset.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-xs capitalize">
                      {asset.type === "image" ? "图片" : asset.type === "video" ? "视频" : asset.type === "document" ? "文档" : asset.type === "template" ? "模板" : "3D模型"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-gray-500">{asset.category}</TableCell>
                  <TableCell className="text-sm text-gray-500">{asset.size}</TableCell>
                  <TableCell className="text-sm text-gray-600">{asset.uploadedBy}</TableCell>
                  <TableCell className="text-sm text-gray-500">{asset.uploadedAt}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {asset.tags.slice(0, 2).map((tag) => (
                        <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Eye className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0"><Download className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-[#EF4444]"><Trash2 className="h-3.5 w-3.5" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
