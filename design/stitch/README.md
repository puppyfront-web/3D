# Stitch 设计稿拉取产物

> 来源：Stitch 项目 `2205002937190653634`
> 拉取时间：2026-07-03
> 方式：Stitch MCP（`https://stitch.googleapis.com/mcp`）直连 JSON-RPC

## 重要说明：MCP 在 ZCode 客户端连不上

`~/.zcode/cli/config.json` 里配置的 `stitch` MCP server **握手失败**：

```
mcp.server.failed  stitch
error: "can't resolve reference #/$defs/ScreenInstance from id #"
toolCount: 0   registeredToolCount: 0
```

原因：Stitch 的工具 schema（如 `generate_variants` / `create_design_system`）在根 `id #` 下用了
`$ref: #/$defs/ScreenInstance`，而 ZCode 的 MCP 客户端在 deref 时无法解析根引用，导致整个 server
连接失败、0 个工具注册。端点本身正常（`initialize` 返回 200）。

**绕过方式**：本目录所有产物都是用 curl 直接打 MCP JSON-RPC 接口拿到的，不依赖客户端 MCP adapter。

## 产物清单

| 文件 | 说明 | Stitch screen/asset ID |
|------|------|------------------------|
| `screenshot_home.png` | 花生ONE 首页原型截图（2560×4552） | `screens/9fabc511d55e4780b729216289391d83` |
| `code_home.html` | 花生ONE 首页原型 HTML 源码 | 同上 |
| `screenshot_workspace.png` | 花生ONE 工作台原型截图（2560×2050） | `screens/29a59c70ca344b1a8d57ff74386135dc` |
| `code_workspace.html` | 花生ONE 工作台原型 HTML 源码 | 同上 |
| `screenshot_design_system_ref.png` | Design System 参考原图（1280×720，原始上传） | `screens/17262242430599962765`（标题 "image.png"，无 HTML） |
| `design_systems.json` | Design System 完整 JSON（含 styleGuidelines + theme） | `assets/dbe894d66bd54580b00ea67a4982fdf1` |
| `design_systems_raw.json` | 原始 MCP 返回（未裁剪） | 同上 |
| `design_system.md` | Design System 的 designMd（YAML token + 文档） | 嵌在 `theme.designMd` 字段 |
| `design_tokens.theme.json` | Material3 主题 token（color / font / roundness） | `theme` 字段 |

## Design System 概览

- **名称**：Enterprise Blueprint
- **风格**：Corporate Modern / 高科技企业 B2B 工作台
- **主色**：`#0052D9`（primary-container），primary `#003DA6`
- **字体**：Inter（headline / body / label 全部）
- **圆角**：8px（ROUND_EIGHT）
- **色板**：LIGHT mode，完整 Material3 named colors（见 `design_tokens.theme.json`）
- **布局**：三栏工作台（左 chat 20-25% / 中 canvas / 右 280-320px 元数据），落地页 12 栅格

## 复现命令

```bash
# 1. list_screens
curl -s -X POST "https://stitch.googleapis.com/mcp" \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $STITCH_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"list_screens","arguments":{"projectId":"2205002937190653634"}}}'

# 2. get_screen（拿单屏详情，含 downloadUrl）
curl -s -X POST "https://stitch.googleapis.com/mcp" \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $STITCH_KEY" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call",
       "params":{"name":"get_screen","arguments":{
         "projectId":"2205002937190653634",
         "name":"projects/2205002937190653634/screens/9fabc511d55e4780b729216289391d83",
         "screenId":"9fabc511d55e4780b729216289391d83"}}}'

# 3. list_design_systems
curl -s -X POST "https://stitch.googleapis.com/mcp" \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $STITCH_KEY" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call",
       "params":{"name":"list_design_systems","arguments":{"projectId":"2205002937190653634"}}}'
```
