import { z } from "zod";

// 共享字段
export const emailField = z
  .string()
  .trim()
  .min(1, "请输入邮箱")
  .regex(/^[^\s@]+@[^\s@]+\.[^\s@]+$/, "邮箱格式不正确");

export const emailCodeField = z
  .string()
  .regex(/^\d{6}$/, "请输入 6 位数字验证码");

export const urlField = z
  .string()
  .trim()
  .refine((v) => v === "" || /^https?:\/\/\S+$/.test(v), {
    message: "链接需以 http:// 或 https:// 开头",
  });

// 登录三模式
export const loginPasswordForm = z.object({
  email: emailField,
  password: z.string().min(1, "请输入密码"),
});

export const loginCodeForm = z.object({
  email: emailField,
  code: emailCodeField,
});

export const resetPasswordForm = z.object({
  email: emailField,
  code: emailCodeField,
  newPassword: z.string().min(6, "新密码至少 6 位"),
});

// 项目向导
export const projectWizardStep1 = z.object({
  projectName: z
    .string()
    .trim()
    .min(1, "请输入工作区名称")
    .max(100, "名称最长 100 字"),
});

export const projectWizardStep2 = z.object({
  companyWebsite: urlField,
});

/** 把 ZodError 展平为 { 字段名: 第一条错误消息 } */
export function zodFieldErrors(error: z.ZodError): Record<string, string> {
  const out: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = issue.path.join(".") || "_";
    if (!out[key]) out[key] = issue.message;
  }
  return out;
}
