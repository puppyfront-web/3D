// Shared domain constants for the admin / workspace frontends.
// Centralised so industry lists stay consistent across modules (previously
// each admin page hard-coded its own divergent list — see PRD §12 review).

/**
 * Canonical industry enumeration used by Cases, ProposalTemplates, and the
 * workspace wizard. Backend stores these as plain String(100), so the union
 * is advisory — but the UI should constrain choices to this set so reporting
 * and filtering stay meaningful.
 */
export const INDUSTRIES = [
  "智慧城市",
  "工业制造",
  "金融科技",
  "能源电力",
  "政务",
  "科技",
  "汽车",
  "商业综合体",
  "文旅",
  "通用",
] as const;

export type Industry = (typeof INDUSTRIES)[number];

/**
 * Visual-style sub-library classification (PRD §12.4 UI 视觉资料库).
 * `null` / empty on the backend means a generic colour-preset style.
 */
export const VISUAL_STYLE_SUB_TYPES = [
  { value: "", label: "颜色预设" },
  { value: "ui_spec", label: "UI 规范" },
  { value: "large_screen", label: "大屏设计案例" },
  { value: "3d_ref", label: "3D 视觉参考" },
  { value: "motion_ref", label: "动效参考" },
] as const;
