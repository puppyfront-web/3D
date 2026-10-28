---
name: AI 团队平台
description: 自建 AI 团队 · AI 大脑（CEO）统一调度的多 Agent 协作工作台（Linear 式克制产品面 + 近黑营销面）
colors:
  primary: "#5e6ad2"
  on-primary: "#ffffff"
  primary-fixed: "#e9eafb"
  on-primary-fixed: "#3c4399"
  inverse-primary: "#828fff"
  secondary: "#0f766e"
  tertiary: "#7c3aed"
  tertiary-fixed: "#ede9fe"
  on-tertiary-fixed: "#2e1065"
  success: "#006c46"
  success-container: "#84f6bc"
  warning: "#733500"
  warning-container: "#ffdbc8"
  error: "#ba1a1a"
  error-container: "#ffdad6"
  surface: "#f8f9fb"
  surface-container-lowest: "#ffffff"
  surface-container-low: "#f3f4f6"
  surface-container: "#edeef0"
  surface-container-high: "#e7e8ea"
  on-surface: "#191c1e"
  on-surface-variant: "#434654"
  outline: "#6e7086"
  outline-variant: "#c9cbe0"
  dark-canvas: "#010102"
  dark-panel: "#0f1011"
  dark-border: "#23252a"
  dark-on-surface: "#f7f8f8"
  dark-on-surface-variant: "#d0d6e0"
typography:
  display:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "56px"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
  xl: "16px"
spacing:
  stack-sm: "8px"
  stack-md: "16px"
  stack-lg: "32px"
  gutter: "24px"
  margin-desktop: "32px"
  container-max: "1440px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 10px"
  button-primary-hover:
    backgroundColor: "#6c78e0"
  button-outline:
    backgroundColor: "{colors.surface-container-lowest}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
    height: "32px"
  input-text:
    backgroundColor: "{colors.surface-container-lowest}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
    height: "36px"
  status-badge:
    backgroundColor: "{colors.surface-container-high}"
    textColor: "{colors.on-surface-variant}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
  card-surface:
    backgroundColor: "{colors.surface-container-lowest}"
    rounded: "{rounded.lg}"
    padding: "24px"
---

# Design System: AI 团队平台

## 1. Overview

**Creative North Star: "The Quiet Control Room"（安静的控制室）**

这是一个让人长时间注视而不疲劳的控制室：用户把任务交给 AI 团队后，界面安静地汇报每一位员工的工作，只在真正需要人类决策的时刻亮起。整套系统由两个面孔构成——**亮色产品面**（工作台/admin，用户全天工作的地方）与**近黑营销面**（`#010102` 画布上的 Linear 式落地页）——共享同一支薰衣草蓝 `#5E6AD2` 作为唯一主色。产品面密度优先、hairline 分隔、动效只表达状态（150–250ms）；营销面允许一次 56px 的大字与克制的 SVG 场景插画。

本系统明确拒绝（承 PRODUCT.md 反引用）：通用 SaaS AI 套壳风（紫色渐变 hero、玻璃拟态、AI 脉冲光球）、3D 幕墙行业垂直痕迹、模板化空话、无溯源的「一键生成」黑箱演示。

**Key Characteristics:**
- 单一主色纪律：薰衣草蓝只出现在主操作、当前选中、「进行中」状态
- 语义色六变体状态徽章（StatusBadge）是全站唯一的状态着色出口
- hairline 边框（`--outline-variant` 1px）承担几乎全部分隔职责，阴影只属于悬浮层
- 全中文文案，动效全部提供 `prefers-reduced-motion` 降级

## 2. Colors

一支薰衣草蓝在两个明度世界之间穿针引线：亮面世界里它稀少而精确，暗面世界里它带着辉光引领。

### Primary
- **薰衣草蓝**（#5e6ad2）：唯一品牌色。主按钮、当前导航项下划线、「进行中」徽章、品牌标识。亮面上 ≤10% 屏面。
- **深靛蓝文本**（#3c4399 / on-primary-fixed）：置于浅薰衣草底（#e9eafb）上的高对比文本，用于选中态徽章与头像。

### Secondary
- **深青**（#0f766e）：图表与次级数据着色；暗面翻转为薄荷绿 #4ade80。

### Tertiary
- **紫罗兰**（#7c3aed）：「审核中/等待人工」信息族；浅紫罗兰底 #ede9fe + 深紫罗兰字 #2e1065 用于 info 徽章。

### Neutral
- **云白面板**（#f8f9fb / surface）：产品面页面底色。
- **纯白卡面**（#ffffff / surface-container-lowest）：卡片、表格、输入框底。
- **墨字**（#191c1e / on-surface）与**岩灰次级字**（#434654 / on-surface-variant，9.4:1）：全部正文只用这两级。
- **雾蓝 hairline**（#c9cbe0 / outline-variant）：边框与分隔线的唯一选择。
- **近黑画布**（#010102）+**碳黑面板**（#0f1011）+**暗 hairline**（#23252a）：营销面与登录页专用（`.theme-dark` 作用域），文本 #f7f8f8 / #d0d6e0。

### Named Rules
**The Token-Only Rule.** 业务代码禁止出现原生灰阶（`gray-*`）与硬编码 hex。一切颜色经 M3 token；状态着色只能经 StatusBadge 六变体（neutral/brand/info/success/warning/error）。全部徽章文本对比度实测 ≥4.5:1。

**The Two Faces Rule.** 暗色只属于营销面与登录页（`.theme-dark` 页级作用域）。工作台与 admin 永远亮色，不做全局暗色模式切换；经 portal 挂载的暗色组件必须在传送门内容上重新应用 `theme-dark` 类。

## 3. Typography

**Display Font:** Inter（系统栈回退：ui-sans-serif / system-ui / PingFang SC / Microsoft YaHei——不加载 web font，CN 构建约束）
**Body Font:** 同一 Inter 栈，`font-feature-settings: "cv02","cv03","cv04","cv11"`
**Label/Mono Font:** 代码/验证码用 SFMono-Regular / Consolas / Menlo

**Character:** 单字族多字重的工程师审美；数字与验证码使用等宽变体以获得终端感。中文以 PingFang/雅黑回退，字号普遍比英文界面大 1px 处理。

### Hierarchy
- **Display**（600，56px，行高 1.08，字距 -0.025em）：仅营销页 hero，一年只用一次的字号。
- **Headline**（600，30–36px）：营销页各 section 标题。
- **Title**（600，20px）：admin 页 h1、卡片标题。
- **Body**（400，14px，行高 1.6）：产品面全部正文；表格密集区允许 12–13px。
- **Label**（500，12px）：徽章、表头、辅助说明。

### Named Rules
**The -0.025em Floor Rule.** Display 级字距最紧 -0.025em（`tracking-tight`）；禁止 `tracking-tighter`（-0.05em，56px 下字母相触）。营销页标题用 `text-wrap: balance`。

## 4. Elevation

**产品面是平的。** 深度由表面明度阶梯（surface-container 五级）与 1px hairline 表达，卡片静止时无阴影。阴影只属于脱离文档流的悬浮层：sticky 工作台导航用 `shadow-sm`，dropdown/dialog/popover 由 radix 提供。营销暗面上「深度」= 面板更亮一档 + 主色辉光（`#5e6ad2` box-shadow glow，仅插画场景元素）。

### Shadow Vocabulary
- **nav-shadow**（`0 1px 2px rgba(0,0,0,0.05)`）：sticky 顶栏。
- **overlay-shadow**（`0 8px 24px rgba(0,0,0,0.12)`）：dialog/dropdown 传送门层。
- 营销 hero 面板允许 `shadow-2xl shadow-black/40`（近黑画布上的唯一大面积阴影）。

### Named Rules
**The Flat-By-Default Rule.** 静止表面无阴影。出现阴影 = 该元素浮在内容之上（sticky/overlay），别无例外。

## 5. Components

### Buttons
- **Shape:** 8px 圆角，紧凑高度 32px（`h-8 px-2.5`），营销面主 CTA 放大到 ~40px 并带 `active:scale-95`。
- **Primary:** 薰衣草蓝底白字（4.7:1），hover 提亮至 #6c78e0（primary-container）。**禁止** `bg-primary hover:bg-primary` 类无操作悬停。
- **Secondary / Outline:** 白底 + outline-variant 边 + 墨字；Ghost 供表格行内图标操作。
- **Focus:** 2px 主色 ring（60% 透明度），全键盘可达。

### Chips — StatusBadge（签名组件）
- **Style:** 4px 圆角胶囊，`2px 8px` 内距，12px 中字。六个语义变体：neutral（灰底岩字）/ brand（浅薰衣草底深靛字 = 进行中）/ info（浅紫底深紫字 = 审核中·等待人工）/ success（薄荷底深绿字 = 完成）/ warning（蜜橙底深棕字 = 预警）/ error（浅红底深红字 = 失败）。
- **State:** 颜色 = 语义状态族，文字 = 具体状态；新增状态先入变体表再上屏。

### Cards / Containers
- **Corner Style:** 12px（rounded-lg）；营销面板 16px；不做 24px+ 圆角。
- **Background:** 纯白卡面于云白页面底上。
- **Border:** 1px outline-variant 全周，静止无阴影。
- **Internal Padding:** 24px；表格内 12–16px。

### Inputs / Fields
- **Style:** 36px 高，白底，1px outline-variant 边，8px 圆角；placeholder 用 on-surface-variant/50。
- **Focus:** 主色 2px ring + 边框透明化。
- **Error:** 边框转 error 色 + 字段下方 12px 红字 + `aria-invalid`/`aria-describedby`（校验统一走 `lib/validators.ts` zod schema）。

### Navigation
- **TopNav**：sticky h-16，营销变体暗底 85% + backdrop-blur，工作台变体白底 shadow-sm；当前项 = 主色 2px 下划线 + `aria-current="page"`。`<md` 收进左侧抽屉（radix Dialog，280px，44px 触达行，焦点圈定 + Esc）。
- **AdminShell**：独立 chrome——h-14 顶栏 + w-60 左侧栏，17 项按平台知识资产/租户资产/平台运营三分组，当前项浅薰衣草底深靛字。

## 6. Do's and Don'ts

### Do:
- **Do** 状态着色一律经 StatusBadge 六变体，新语义先扩变体表。
- **Do** 文本只使用 on-surface / on-surface-variant 两级（9.4:1+）；空态文案也必须 ≥4.5:1。
- **Do** 全部表单校验走 `lib/validators.ts`（zod），错误显示在字段近旁而非只有顶部 banner。
- **Do** 动效 150–250ms、只表达状态（流式/加载/展开），全部带 `motion-reduce` 降级。
- **Do** 移动端导航必须可用（抽屉已内建），触达目标 ≥44px。

### Don't:
- **Don't** 紫色渐变 hero、玻璃拟态卡片、AI 脉冲光球装饰（PRODUCT.md 反引用，逐字执行）。
- **Don't** 在业务代码写 `gray-*` 或硬编码 hex——2026-10-28 已全量清除，回归即错。
- **Don't** `border-left/right` > 1px 作彩色侧条纹；用全周边框、底色或前导图标。
- **Don't** Display 字距紧于 -0.025em（`tracking-tighter` 违禁）。
- **Don't** 工作台/admin 出现暗色主题或 `.theme-dark`；暗色只属于营销面与登录页。
- **Don't** 无溯源的「AI 一键生成」演示内容；占位必须标注「示意」。
