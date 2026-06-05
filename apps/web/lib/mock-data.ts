import {
  Project,
  CompanyAnalysis,
  Proposal,
  VisualProject,
  ReviewChecklist,
  Asset,
  CaseItem,
  SOPWorkflow,
  ProposalTemplate,
  PromptTemplate,
  VisualStyle,
  TechnicalRule,
  QualityRule,
  Evaluation,
} from "@/types";

// ============================================================
// Projects
// ============================================================

export const mockProjects: Project[] = [
  {
    id: "proj-001",
    name: "智慧城市数字化展厅方案",
    client: "深圳市科技创新委员会",
    industry: "智慧城市",
    status: "proposal_draft",
    priority: "high",
    createdAt: "2026-05-20",
    updatedAt: "2026-05-28",
    dueDate: "2026-06-15",
    description: "为深圳市科创委打造智慧城市数字化展厅，包含3D可视化大屏、交互式数据展示系统、城市运行态势感知平台等核心模块。",
    progress: 65,
    assignee: "张明",
    tags: ["3D可视化", "智慧城市", "大屏"],
  },
  {
    id: "proj-002",
    name: "新能源汽车品牌官网升级",
    client: "蔚来汽车",
    industry: "新能源汽车",
    status: "visual_design",
    priority: "high",
    createdAt: "2026-05-18",
    updatedAt: "2026-06-01",
    dueDate: "2026-06-20",
    description: "为蔚来汽车升级品牌官网，引入3D车辆配置器、沉浸式品牌体验页面和智能客服系统集成。",
    progress: 78,
    assignee: "李婷",
    tags: ["品牌升级", "3D配置器", "Web3D"],
  },
  {
    id: "proj-003",
    name: "工业互联网平台提案",
    client: "三一重工",
    industry: "工业制造",
    status: "company_analysis",
    priority: "medium",
    createdAt: "2026-05-25",
    updatedAt: "2026-06-02",
    dueDate: "2026-07-01",
    description: "为三一重工设计工业互联网平台解决方案，涵盖设备远程监控、预测性维护、智能排产等核心功能。",
    progress: 35,
    assignee: "王磊",
    tags: ["工业互联网", "IoT", "数字孪生"],
  },
  {
    id: "proj-004",
    name: "医疗影像AI诊断系统方案",
    client: "联影医疗",
    industry: "医疗健康",
    status: "review",
    priority: "high",
    createdAt: "2026-05-10",
    updatedAt: "2026-06-03",
    dueDate: "2026-06-10",
    description: "为联影医疗设计基于AI的医疗影像辅助诊断系统方案，包括CT/MRI智能分析、病灶标注、辅助报告生成等模块。",
    progress: 90,
    assignee: "赵雪",
    tags: ["AI", "医疗影像", "深度学习"],
  },
  {
    id: "proj-005",
    name: "跨境电商平台3D展示方案",
    client: "SHEIN",
    industry: "跨境电商",
    status: "approved",
    priority: "medium",
    createdAt: "2026-04-28",
    updatedAt: "2026-05-30",
    dueDate: "2026-06-05",
    description: "为SHEIN设计跨境电商3D商品展示方案，实现服装3D试穿、商品360度展示和AR试妆功能。",
    progress: 100,
    assignee: "陈晨",
    tags: ["3D展示", "AR试穿", "电商"],
  },
  {
    id: "proj-006",
    name: "金融风控可视化平台",
    client: "招商银行",
    industry: "金融科技",
    status: "in_progress",
    priority: "low",
    createdAt: "2026-06-01",
    updatedAt: "2026-06-04",
    dueDate: "2026-07-15",
    description: "为招商银行设计金融风控数据可视化平台，包含实时风险监控大屏、异常交易检测可视化和客户画像分析。",
    progress: 15,
    assignee: "刘洋",
    tags: ["数据可视化", "风控", "金融"],
  },
];

// ============================================================
// Company Analysis
// ============================================================

export const mockCompanyAnalysis: CompanyAnalysis = {
  companyId: "comp-001",
  projectName: "智慧城市数字化展厅方案",
  companyName: "深圳市科技创新委员会",
  industry: "智慧城市",
  overview:
    "深圳市科技创新委员会是深圳市政府直属机构，负责全市科技创新发展战略制定与实施。近年来大力推进智慧城市建设，年均信息化投入超过50亿元。重点关注物联网、大数据、人工智能等前沿技术在城市治理中的应用，已建成覆盖全市的政务云平台和城市大脑系统。",
  businessModel:
    "政府机构运作模式，通过财政拨款支持科技创新项目。采用PPP模式引入社会资本参与智慧城市项目建设，项目验收标准严格，要求供应商具备CMMI5级认证和信息安全等级保护三级资质。采购流程通常包括需求调研、方案评审、招标采购、实施交付、验收评估五个阶段。",
  competitiveAnalysis: [
    {
      competitor: "华为技术有限公司",
      strength: "全栈智慧城市解决方案，生态合作伙伴众多",
      weakness: "价格偏高，定制化能力有限",
      marketShare: "28%",
    },
    {
      competitor: "阿里云",
      strength: "城市大脑产品成熟，数据处理能力强",
      weakness: "政务领域品牌信任度待提升",
      marketShare: "22%",
    },
    {
      competitor: "腾讯云",
      strength: "微信生态优势，用户触达能力强",
      weakness: "行业解决方案深度不足",
      marketShare: "18%",
    },
    {
      competitor: "中兴通讯",
      strength: "通信基础设施优势，成本控制好",
      weakness: "软件平台能力相对薄弱",
      marketShare: "15%",
    },
  ],
  financialHighlights: [
    { metric: "年度信息化预算", value: "52.3亿元", trend: "up", year: "2026" },
    { metric: "智慧城市项目数", value: "186个", trend: "up", year: "2026" },
    { metric: "供应商数量", value: "340+", trend: "up", year: "2026" },
    { metric: "平均项目周期", value: "8.5个月", trend: "down", year: "2026" },
    { metric: "项目成功率", value: "92.3%", trend: "stable", year: "2026" },
  ],
  technologyAssessment:
    "客户技术栈以Java/Spring Cloud微服务架构为主，前端使用Vue.js。已部署Kubernetes容器编排平台，数据库采用OceanBase+PostgreSQL混合方案。对新技术持开放态度，但对系统稳定性和安全性要求极高。3D可视化方面需求明确，需要支持WebGL/WebGPU渲染，兼容主流浏览器。",
  risks: [
    {
      category: "技术风险",
      description: "3D渲染性能在大规模场景下可能出现瓶颈",
      severity: "medium",
      mitigation: "采用LOD技术和实例化渲染优化，提前进行性能基准测试",
    },
    {
      category: "进度风险",
      description: "政府审批流程较长，可能影响项目交付进度",
      severity: "high",
      mitigation: "提前了解审批流程，设置合理里程碑，预留缓冲时间",
    },
    {
      category: "合规风险",
      description: "政务数据安全要求高，需满足等保三级标准",
      severity: "high",
      mitigation: "聘请专业安全顾问，在方案中明确安全架构设计",
    },
  ],
  recommendations: [
    "采用Three.js + WebGPU方案实现3D渲染，确保跨平台兼容性",
    "结合客户现有Vue.js技术栈，提供Vue组件化集成方案",
    "建议引入数字孪生概念，增强方案的差异化和前瞻性",
    "在方案中突出数据安全架构设计，提前回应合规关切",
    "提供分期交付方案，降低项目整体风险",
  ],
  generatedAt: "2026-06-02T14:30:00Z",
};

// ============================================================
// Proposal
// ============================================================

export const mockProposal: Proposal = {
  id: "prop-001",
  projectId: "proj-001",
  title: "深圳市科技创新委员会智慧城市数字化展厅建设方案",
  sections: [
    {
      id: "sec-001",
      title: "项目概述",
      content:
        "本项目旨在为深圳市科技创新委员会建设一套现代化的智慧城市数字化展厅系统，通过3D可视化、数字孪生、实时数据融合等前沿技术，全方位展示深圳智慧城市建设成果与未来规划。\n\n项目核心目标：\n1. 建设覆盖全市的3D城市数字孪生底座\n2. 实现城市运行态势的实时可视化监控\n3. 打造沉浸式的智慧城市体验空间\n4. 构建可扩展的数据中台支撑体系",
      order: 1,
      status: "approved",
    },
    {
      id: "sec-002",
      title: "技术方案",
      content:
        "本方案采用业界领先的技术架构，确保系统的高性能、高可用性和可扩展性。\n\n核心技术栈：\n- 前端渲染引擎：Three.js + WebGPU\n- 后端服务：Spring Cloud微服务架构\n- 数据中台：Apache Flink + Kafka实时数据处理\n- 3D建模：基于摄影测量的城市级三维重建\n- 数字孪生：IoT数据接入与实时映射\n\n系统架构分为四层：\n1. 数据采集层：物联网传感器、政务数据接口\n2. 数据处理层：实时流处理、数据融合\n3. 服务支撑层：微服务集群、API网关\n4. 展示交互层：3D渲染引擎、多屏适配",
      order: 2,
      status: "review",
    },
    {
      id: "sec-003",
      title: "实施计划",
      content:
        "项目总工期预计8个月，分为四个阶段推进：\n\n第一阶段（第1-2月）：需求调研与方案深化\n- 完成详细需求调研\n- 完成3D建模区域确认\n- 确定数据接入接口规范\n\n第二阶段（第3-4月）：核心开发\n- 完成3D城市底座建设\n- 完成数据中台搭建\n- 完成核心功能模块开发\n\n第三阶段（第5-6月）：集成联调\n- 系统集成测试\n- 性能优化与调优\n- 用户体验优化\n\n第四阶段（第7-8月）：部署验收\n- 生产环境部署\n- 用户培训\n- 项目验收交付",
      order: 3,
      status: "draft",
    },
    {
      id: "sec-004",
      title: "投资概算",
      content:
        "项目总投资概算：¥3,850万元\n\n一、软件系统开发：¥1,680万元\n  - 3D可视化引擎：¥580万\n  - 数据中台：¥420万\n  - 业务功能模块：¥380万\n  - 系统集成与测试：¥300万\n\n二、硬件设备：¥1,200万元\n  - LED展示大屏：¥480万\n  - 服务器及网络设备：¥380万\n  - 交互设备：¥340万\n\n三、3D建模与数据：¥620万元\n  - 城市三维建模：¥420万\n  - 数据接入与治理：¥200万\n\n四、项目管理与培训：¥350万元\n\n五、运维服务（首年）：¥200万元",
      order: 4,
      status: "draft",
    },
    {
      id: "sec-005",
      title: "团队配置",
      content:
        "项目团队核心成员配置：\n\n项目经理：1人，PMP认证，10年以上政务项目管理经验\n技术总监：1人，精通3D可视化与分布式系统架构\n前端开发：4人，Three.js/WebGL专家\n后端开发：6人，Spring Cloud微服务开发\n3D建模师：3人，城市级三维建模经验\n数据工程师：2人，实时数据处理与数据治理\n测试工程师：2人，自动化测试与性能测试\nUI/UX设计师：2人，政务类产品设计经验\n\n总计核心团队21人，可根据项目需求动态调整。",
      order: 5,
      status: "draft",
    },
  ],
  totalWords: 4850,
  lastEditedAt: "2026-06-03T10:15:00Z",
  version: 3,
};

// ============================================================
// Visual Projects
// ============================================================

export const mockVisualProjects: VisualProject[] = [
  {
    id: "vp-001",
    projectId: "proj-001",
    name: "智慧城市展厅主视觉",
    prompt: "A futuristic smart city control center with holographic displays, blue and cyan color scheme, ultra-modern design, photorealistic 3D render, 8K quality",
    style: "写实科技风",
    size: "1920x1080",
    images: [
      {
        id: "img-001",
        url: "/placeholder-visual-1.jpg",
        prompt: "Smart city dashboard with 3D buildings and real-time data overlays",
        status: "completed",
        createdAt: "2026-06-01T09:00:00Z",
      },
      {
        id: "img-002",
        url: "/placeholder-visual-2.jpg",
        prompt: "Futuristic city panorama with IoT network visualization",
        status: "completed",
        createdAt: "2026-06-01T09:05:00Z",
      },
      {
        id: "img-003",
        url: "/placeholder-visual-3.jpg",
        prompt: "Close-up of holographic data display in smart city center",
        status: "completed",
        createdAt: "2026-06-01T09:10:00Z",
      },
    ],
    createdAt: "2026-06-01T09:00:00Z",
  },
];

// ============================================================
// Review Checklists
// ============================================================

export const mockReviewChecklists: ReviewChecklist[] = [
  {
    id: "rc-001",
    category: "内容完整性",
    items: [
      { id: "ri-001", description: "方案概述清晰完整", status: "pass", comment: "符合要求" },
      { id: "ri-002", description: "技术架构描述详尽", status: "pass", comment: "技术栈选型合理" },
      { id: "ri-003", description: "实施计划时间节点明确", status: "warning", comment: "第三阶段时间偏紧，建议增加缓冲" },
      { id: "ri-004", description: "投资概算包含所有费用项", status: "pass", comment: "费用覆盖全面" },
      { id: "ri-005", description: "团队配置满足项目需求", status: "pass", comment: "人员配置合理" },
    ],
  },
  {
    id: "rc-002",
    category: "技术可行性",
    items: [
      { id: "ri-006", description: "3D渲染性能满足要求", status: "pass", comment: "LOD方案可行" },
      { id: "ri-007", description: "数据接入方案可行", status: "pass", comment: "已验证接口兼容性" },
      { id: "ri-008", description: "系统安全等级达标", status: "warning", comment: "需补充等保三级认证材料" },
      { id: "ri-009", description: "跨平台兼容性验证", status: "fail", comment: "Safari浏览器WebGPU兼容性需解决" },
    ],
  },
  {
    id: "rc-003",
    category: "商务条款",
    items: [
      { id: "ri-010", description: "报价合理有竞争力", status: "pass", comment: "符合市场行情" },
      { id: "ri-011", description: "付款条件清晰", status: "pass", comment: "分期付款方案可行" },
      { id: "ri-012", description: "售后服务承诺明确", status: "pending", comment: "" },
    ],
  },
];

// ============================================================
// Admin: Assets
// ============================================================

export const mockAssets: Asset[] = [
  { id: "ast-001", name: "智慧城市3D模型包", type: "model", category: "3D模型", url: "/assets/models/city.zip", size: "2.3GB", uploadedAt: "2026-05-15", uploadedBy: "张明", tags: ["城市", "3D", "建筑"] },
  { id: "ast-002", name: "科技感背景素材", type: "image", category: "背景图", url: "/assets/images/tech-bg.jpg", size: "15MB", uploadedAt: "2026-05-18", uploadedBy: "李婷", tags: ["背景", "科技", "蓝色"] },
  { id: "ast-003", name: "产品演示视频模板", type: "video", category: "视频", url: "/assets/videos/demo.mp4", size: "580MB", uploadedAt: "2026-05-20", uploadedBy: "王磊", tags: ["视频", "演示", "模板"] },
  { id: "ast-004", name: "标准方案模板v3.0", type: "template", category: "文档模板", url: "/assets/templates/proposal-v3.docx", size: "2.5MB", uploadedAt: "2026-05-22", uploadedBy: "赵雪", tags: ["模板", "方案", "标准"] },
  { id: "ast-005", name: "UI组件库设计稿", type: "document", category: "设计文档", url: "/assets/docs/ui-kit.fig", size: "45MB", uploadedAt: "2026-05-25", uploadedBy: "陈晨", tags: ["UI", "组件库", "设计"] },
  { id: "ast-006", name: "数据可视化图标集", type: "image", category: "图标", url: "/assets/images/icons.zip", size: "120MB", uploadedAt: "2026-05-28", uploadedBy: "刘洋", tags: ["图标", "可视化", "数据"] },
];

// ============================================================
// Admin: Cases
// ============================================================

export const mockCases: CaseItem[] = [
  { id: "case-001", title: "深圳市交通局智慧交通3D可视化平台", client: "深圳市交通运输局", industry: "智慧交通", outcome: "成功交付，客户满意度95分", highlights: ["实时路况3D展示", "信号灯智能调控", "事故预警系统"], createdAt: "2026-03-15", status: "published" },
  { id: "case-002", title: "广州地铁数字孪生运维系统", client: "广州地铁集团", industry: "轨道交通", outcome: "降低运维成本30%，提升响应速度50%", highlights: ["车站3D数字孪生", "设备预测性维护", "应急演练仿真"], createdAt: "2026-02-20", status: "published" },
  { id: "case-003", title: "招商银行金融数据可视化大屏", client: "招商银行总行", industry: "金融科技", outcome: "管理层决策效率提升40%", highlights: ["实时风控监控", "全球业务态势", "客户画像分析"], createdAt: "2026-01-10", status: "published" },
  { id: "case-004", title: "宁德时代智能工厂3D仿真", client: "宁德时代", industry: "智能制造", outcome: "产线优化节省成本1200万/年", highlights: ["产线3D仿真", "工艺流程优化", "质量追溯可视化"], createdAt: "2026-04-05", status: "draft" },
  { id: "case-005", title: "国家电网变电站智能巡检系统", client: "国家电网", industry: "能源电力", outcome: "巡检效率提升60%，故障发现率提升35%", highlights: ["变电站3D建模", "无人机巡检路径", "缺陷AI识别"], createdAt: "2026-04-20", status: "archived" },
];

// ============================================================
// Admin: SOP Workflows
// ============================================================

export const mockSOPWorkflows: SOPWorkflow[] = [
  {
    id: "sop-001",
    name: "标准方案编制流程",
    description: "从需求分析到方案交付的标准SOP流程",
    category: "方案编制",
    isActive: true,
    createdAt: "2026-01-15",
    updatedAt: "2026-05-20",
    steps: [
      { id: "s1-001", name: "需求收集与分析", description: "通过客户访谈、文档分析等方式收集项目需求", order: 1, agentType: "需求分析Agent", estimatedTime: "2天", requiredInputs: ["客户信息", "项目背景"], outputs: ["需求文档", "需求分析报告"] },
      { id: "s1-002", name: "企业调研与分析", description: "对目标客户进行全面的商业和技术调研", order: 2, agentType: "企业分析Agent", estimatedTime: "1天", requiredInputs: ["企业信息", "行业数据"], outputs: ["企业分析报告", "竞品分析"] },
      { id: "s1-003", name: "方案框架设计", description: "基于需求和分析结果设计方案框架", order: 3, agentType: "方案设计Agent", estimatedTime: "2天", requiredInputs: ["需求文档", "分析报告"], outputs: ["方案框架", "技术架构图"] },
      { id: "s1-004", name: "内容撰写与生成", description: "基于框架生成各章节详细内容", order: 4, agentType: "内容生成Agent", estimatedTime: "3天", requiredInputs: ["方案框架", "案例库", "模板库"], outputs: ["方案初稿"] },
      { id: "s1-005", name: "视觉素材制作", description: "根据方案需求制作3D渲染图、信息图等视觉素材", order: 5, agentType: "视觉生成Agent", estimatedTime: "2天", requiredInputs: ["视觉需求", "品牌规范"], outputs: ["视觉素材包"] },
      { id: "s1-006", name: "质量审核与修订", description: "对方案进行全面的质量审核和修订", order: 6, agentType: "审核Agent", estimatedTime: "1天", requiredInputs: ["方案初稿", "质量标准"], outputs: ["审核报告", "修订建议"] },
    ],
  },
  {
    id: "sop-002",
    name: "快速响应方案流程",
    description: "针对紧急需求的快速方案生成流程",
    category: "快速响应",
    isActive: true,
    createdAt: "2026-03-10",
    updatedAt: "2026-05-15",
    steps: [
      { id: "s2-001", name: "快速需求评估", description: "快速评估客户需求和项目可行性", order: 1, agentType: "需求分析Agent", estimatedTime: "4小时", requiredInputs: ["客户基本信息"], outputs: ["需求摘要", "可行性评估"] },
      { id: "s2-002", name: "模板匹配与生成", description: "从模板库中匹配最合适的方案模板并快速填充", order: 2, agentType: "模板匹配Agent", estimatedTime: "2小时", requiredInputs: ["需求摘要"], outputs: ["方案草稿"] },
      { id: "s2-003", name: "快速审核", description: "自动化质量审核，重点检查关键要素", order: 3, agentType: "审核Agent", estimatedTime: "1小时", requiredInputs: ["方案草稿"], outputs: ["审核结果"] },
    ],
  },
];

// ============================================================
// Admin: Proposal Templates
// ============================================================

export const mockProposalTemplates: ProposalTemplate[] = [
  {
    id: "pt-001",
    name: "智慧城市标准方案模板",
    category: "智慧城市",
    industry: "政务",
    description: "适用于智慧城市类项目的标准方案模板，包含完整章节结构",
    usageCount: 45,
    createdAt: "2026-01-01",
    updatedAt: "2026-05-10",
    sections: [
      { id: "ps-001", title: "项目概述", defaultContent: "请在此填写项目概述...", required: true },
      { id: "ps-002", title: "需求分析", defaultContent: "请在此填写需求分析...", required: true },
      { id: "ps-003", title: "技术方案", defaultContent: "请在此填写技术方案...", required: true },
      { id: "ps-004", title: "实施计划", defaultContent: "请在此填写实施计划...", required: true },
      { id: "ps-005", title: "投资概算", defaultContent: "请在此填写投资概算...", required: false },
    ],
  },
  {
    id: "pt-002",
    name: "工业互联网方案模板",
    category: "工业互联网",
    industry: "工业制造",
    description: "适用于工业互联网和智能制造类项目",
    usageCount: 28,
    createdAt: "2026-02-15",
    updatedAt: "2026-05-08",
    sections: [
      { id: "ps-006", title: "项目背景与目标", defaultContent: "请在此填写项目背景...", required: true },
      { id: "ps-007", title: "现状分析", defaultContent: "请在此填写现状分析...", required: true },
      { id: "ps-008", title: "解决方案", defaultContent: "请在此填写解决方案...", required: true },
      { id: "ps-009", title: "技术架构", defaultContent: "请在此填写技术架构...", required: true },
    ],
  },
  {
    id: "pt-003",
    name: "企业数字化转型方案模板",
    category: "数字化转型",
    industry: "通用",
    description: "适用于各类企业数字化转型项目",
    usageCount: 62,
    createdAt: "2025-12-01",
    updatedAt: "2026-04-20",
    sections: [
      { id: "ps-010", title: "企业诊断", defaultContent: "请在此填写企业诊断...", required: true },
      { id: "ps-011", title: "转型路径", defaultContent: "请在此填写转型路径...", required: true },
      { id: "ps-012", title: "技术选型", defaultContent: "请在此填写技术选型...", required: true },
      { id: "ps-013", title: "ROI分析", defaultContent: "请在此填写ROI分析...", required: false },
    ],
  },
];

// ============================================================
// Admin: Prompt Templates
// ============================================================

export const mockPromptTemplates: PromptTemplate[] = [
  {
    id: "prmpt-001",
    name: "企业背景分析Prompt",
    category: "企业分析",
    prompt: "请对以下企业进行全面的背景分析，包括企业历史、主营业务、组织架构、技术实力和市场地位。\n\n企业名称：{{company_name}}\n所属行业：{{industry}}\n分析重点：{{focus_area}}",
    description: "用于生成企业背景分析报告的标准Prompt",
    usageCount: 156,
    createdAt: "2026-01-10",
    variables: [
      { name: "company_name", description: "目标企业名称", defaultValue: "", required: true },
      { name: "industry", description: "所属行业", defaultValue: "科技", required: true },
      { name: "focus_area", description: "分析重点领域", defaultValue: "技术与市场", required: false },
    ],
  },
  {
    id: "prmpt-002",
    name: "技术方案生成Prompt",
    category: "方案生成",
    prompt: "基于以下需求信息，生成一份详细的技术方案，包括技术架构设计、关键技术选型、系统模块划分和实施路径。\n\n项目类型：{{project_type}}\n核心技术需求：{{core_requirements}}\n技术约束：{{constraints}}\n预期用户规模：{{user_scale}}",
    description: "用于自动生成技术方案章节的Prompt",
    usageCount: 89,
    createdAt: "2026-02-05",
    variables: [
      { name: "project_type", description: "项目类型", defaultValue: "", required: true },
      { name: "core_requirements", description: "核心技术需求", defaultValue: "", required: true },
      { name: "constraints", description: "技术约束条件", defaultValue: "无特殊约束", required: false },
      { name: "user_scale", description: "预期用户规模", defaultValue: "1000+", required: false },
    ],
  },
  {
    id: "prmpt-003",
    name: "竞品分析Prompt",
    category: "企业分析",
    prompt: "请对以下企业在{{industry}}领域的竞争对手进行深入分析，对比各竞争对手的优势、劣势、市场策略和产品差异化。\n\n目标企业：{{company_name}}\n行业：{{industry}}\n竞争对手列表：{{competitors}}\n分析维度：{{dimensions}}",
    description: "用于竞品对比分析的Prompt模板",
    usageCount: 73,
    createdAt: "2026-03-12",
    variables: [
      { name: "company_name", description: "目标企业", defaultValue: "", required: true },
      { name: "industry", description: "所属行业", defaultValue: "", required: true },
      { name: "competitors", description: "竞争对手列表", defaultValue: "", required: true },
      { name: "dimensions", description: "分析维度", defaultValue: "产品、技术、市场、价格", required: false },
    ],
  },
];

// ============================================================
// Admin: Visual Styles
// ============================================================

export const mockVisualStyles: VisualStyle[] = [
  { id: "vs-001", name: "科技蓝风格", description: "以深蓝色为主色调的科技风格，适合智慧城市、工业类项目", previewUrl: "/placeholder-style-1.jpg", parameters: { primaryColor: "#1E3A5F", accentColor: "#00D4FF", bgStyle: "dark-gradient" }, category: "科技", isActive: true, createdAt: "2026-01-01" },
  { id: "vs-002", name: "简约商务风", description: "简洁专业的商务风格，适合金融、咨询类项目", previewUrl: "/placeholder-style-2.jpg", parameters: { primaryColor: "#2D3436", accentColor: "#0984E3", bgStyle: "light-clean" }, category: "商务", isActive: true, createdAt: "2026-01-15" },
  { id: "vs-003", name: "自然生态风", description: "以绿色为主色调的自然风格，适合环保、农业类项目", previewUrl: "/placeholder-style-3.jpg", parameters: { primaryColor: "#2D6A4F", accentColor: "#95D5B2", bgStyle: "nature-gradient" }, category: "生态", isActive: true, createdAt: "2026-02-01" },
  { id: "vs-004", name: "未来赛博风", description: "赛博朋克风格的未来感设计，适合前沿科技展示", previewUrl: "/placeholder-style-4.jpg", parameters: { primaryColor: "#0D0221", accentColor: "#FF00FF", bgStyle: "cyber-neon" }, category: "科技", isActive: false, createdAt: "2026-02-20" },
  { id: "vs-005", name: "温暖医疗风", description: "柔和温暖的医疗健康风格，适合医疗、养老类项目", previewUrl: "/placeholder-style-5.jpg", parameters: { primaryColor: "#5B8C5A", accentColor: "#E8A87C", bgStyle: "warm-soft" }, category: "医疗", isActive: true, createdAt: "2026-03-05" },
];

// ============================================================
// Admin: Technical Rules
// ============================================================

export const mockTechnicalRules: TechnicalRule[] = [
  { id: "tr-001", name: "3D模型面数限制", category: "3D渲染", description: "单个3D模型面数不应超过500万面，确保Web端流畅渲染", rule: "model.faceCount <= 5000000", severity: "critical", isActive: true, createdAt: "2026-01-10" },
  { id: "tr-002", name: "首屏加载时间", category: "性能", description: "页面首屏加载时间不超过3秒", rule: "page.firstLoadTime <= 3000", severity: "critical", isActive: true, createdAt: "2026-01-10" },
  { id: "tr-003", name: "WebGL兼容性", category: "兼容性", description: "3D渲染必须兼容WebGL 2.0，降级方案支持WebGL 1.0", rule: "renderer.version >= 'webgl2' || fallback('webgl1')", severity: "warning", isActive: true, createdAt: "2026-02-05" },
  { id: "tr-004", name: "API响应时间", category: "性能", description: "API平均响应时间不超过500ms", rule: "api.avgResponseTime <= 500", severity: "warning", isActive: true, createdAt: "2026-02-15" },
  { id: "tr-005", name: "数据加密传输", category: "安全", description: "所有数据传输必须使用TLS 1.3加密", rule: "transport.protocol >= 'TLS1.3'", severity: "critical", isActive: true, createdAt: "2026-03-01" },
];

// ============================================================
// Admin: Quality Rules
// ============================================================

export const mockQualityRules: QualityRule[] = [
  {
    id: "qr-001",
    name: "方案内容质量标准",
    category: "内容质量",
    description: "方案内容必须满足的基本质量要求",
    passingScore: 80,
    isActive: true,
    createdAt: "2026-01-15",
    criteria: [
      { id: "qc-001", description: "方案结构完整，包含所有必需章节", weight: 20, scoringGuide: "完整包含得20分，缺少一章扣5分" },
      { id: "qc-002", description: "技术方案描述清晰，技术选型合理", weight: 25, scoringGuide: "清晰合理得25分，描述模糊扣10分" },
      { id: "qc-003", description: "数据引用准确，来源可追溯", weight: 15, scoringGuide: "全部准确得15分，一处错误扣3分" },
      { id: "qc-004", description: "语言表达专业、流畅", weight: 20, scoringGuide: "专业流畅得20分，有语法错误扣2分/处" },
      { id: "qc-005", description: "符合客户行业特点和需求", weight: 20, scoringGuide: "高度匹配得20分，偏题扣10分" },
    ],
  },
  {
    id: "qr-002",
    name: "视觉设计质量标准",
    category: "视觉质量",
    description: "视觉素材和整体设计风格的质量要求",
    passingScore: 75,
    isActive: true,
    createdAt: "2026-02-01",
    criteria: [
      { id: "qc-006", description: "设计风格统一，色彩搭配协调", weight: 30, scoringGuide: "统一协调得30分" },
      { id: "qc-007", description: "图片分辨率满足输出要求", weight: 25, scoringGuide: "满足要求得25分" },
      { id: "qc-008", description: "信息图表清晰易读", weight: 25, scoringGuide: "清晰易读得25分" },
      { id: "qc-009", description: "品牌元素应用一致", weight: 20, scoringGuide: "一致应用得20分" },
    ],
  },
];

// ============================================================
// Admin: Evaluations
// ============================================================

export const mockEvaluations: Evaluation[] = [
  {
    id: "eval-001",
    projectId: "proj-001",
    projectName: "智慧城市数字化展厅方案",
    evaluatedAt: "2026-06-03T16:00:00Z",
    evaluator: "系统自动评估",
    overallScore: 87,
    status: "completed",
    categories: [
      { name: "内容完整性", score: 90, maxScore: 100, comments: "方案结构完整，各章节内容充实" },
      { name: "技术可行性", score: 85, maxScore: 100, comments: "技术方案合理，需关注WebGPU兼容性" },
      { name: "商务合规性", score: 88, maxScore: 100, comments: "报价合理，付款条件清晰" },
      { name: "视觉呈现", score: 82, maxScore: 100, comments: "设计风格统一，部分素材可优化" },
    ],
  },
  {
    id: "eval-002",
    projectId: "proj-004",
    projectName: "医疗影像AI诊断系统方案",
    evaluatedAt: "2026-06-02T11:30:00Z",
    evaluator: "系统自动评估",
    overallScore: 92,
    status: "completed",
    categories: [
      { name: "内容完整性", score: 95, maxScore: 100, comments: "方案非常完整，覆盖所有关键要素" },
      { name: "技术可行性", score: 90, maxScore: 100, comments: "AI技术方案成熟，与现有系统兼容性好" },
      { name: "商务合规性", score: 92, maxScore: 100, comments: "定价有竞争力，服务承诺明确" },
      { name: "视觉呈现", score: 88, maxScore: 100, comments: "医疗风格设计专业，配色温馨" },
    ],
  },
  {
    id: "eval-003",
    projectId: "proj-003",
    projectName: "工业互联网平台提案",
    evaluatedAt: "2026-06-04T09:00:00Z",
    evaluator: "系统自动评估",
    overallScore: 72,
    status: "pending",
    categories: [
      { name: "内容完整性", score: 78, maxScore: 100, comments: "部分章节内容尚待补充" },
      { name: "技术可行性", score: 70, maxScore: 100, comments: "技术架构待进一步细化" },
      { name: "商务合规性", score: 68, maxScore: 100, comments: "投资概算需要细化" },
      { name: "视觉呈现", score: 72, maxScore: 100, comments: "视觉素材仍在制作中" },
    ],
  },
];
