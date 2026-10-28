import { cn } from "@/lib/utils";

/**
 * 全站统一的状态徽章。
 * 颜色 = 语义状态族（成功/警告/错误/品牌进行中/信息审核/中性），
 * 文字 = 具体状态。禁止在业务代码里另建 hex 状态配色。
 */
const variants = {
  neutral: "bg-surface-container-high text-on-surface-variant",
  brand: "bg-primary-fixed text-on-primary-fixed",
  info: "bg-tertiary-fixed text-on-tertiary-fixed",
  success: "bg-success-container text-success",
  warning: "bg-warning-container text-warning",
  error: "bg-error-container text-error",
} as const;

export type StatusBadgeVariant = keyof typeof variants;

export function StatusBadge({
  variant = "neutral",
  className,
  children,
}: {
  variant?: StatusBadgeVariant;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
