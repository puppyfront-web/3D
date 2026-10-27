"use client";

// Login page — three modes on one route:
//   password : email + password (classic)
//   code     : email + one-time verification code (mock provider surfaces
//              the code as devCode until SMTP is configured)
//   reset    : email + code + new password (password recovery)
// 401s anywhere in the app redirect here (lib/api.ts interceptor).

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, Loader2, LogIn, Mail, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import {
  login,
  loginWithEmailCode,
  resetPasswordWithEmailCode,
  sendEmailCode,
} from "@/lib/api";
import { setToken, setStoredUser, isAuthenticated } from "@/lib/auth";
import { APP_NAME, APP_FULL_NAME, APP_TAGLINE } from "@/lib/constants";

type Mode = "password" | "code" | "reset";

const RESEND_SECONDS = 60;

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  // Already logged in → redirect to workspace
  useEffect(() => {
    if (isAuthenticated()) {
      router.replace("/workspace/projects");
    }
  }, [router]);

  // Resend countdown ticker
  useEffect(() => {
    if (countdown <= 0) return;
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setDevCode(null);
  }

  async function handleSendCode() {
    if (!email.trim()) {
      setError("请先输入邮箱");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const purpose = mode === "reset" ? "reset" : "login";
      const res = await sendEmailCode(email.trim(), purpose);
      setCountdown(RESEND_SECONDS);
      setDevCode(res.devCode ?? null);
      toast.success("验证码已发送，请查收邮箱");
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setLoading(false);
    }
  }

  async function completeLogin(token: string, user?: { name?: string; email?: string }) {
    setToken(token);
    setStoredUser({ name: user?.name, email: user?.email });
    toast.success(`欢迎回来，${user?.name || email}`);
    router.replace("/workspace/projects");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (mode === "password" && (!email.trim() || !password.trim())) {
      setError("请输入邮箱和密码");
      return;
    }
    if (mode !== "password" && !email.trim()) {
      setError("请输入邮箱");
      return;
    }
    if (mode !== "password" && !code.trim()) {
      setError("请输入邮箱验证码");
      return;
    }
    if (mode === "reset" && newPassword.trim().length < 6) {
      setError("新密码至少 6 位");
      return;
    }

    setLoading(true);
    try {
      if (mode === "password") {
        const { token, user } = await login(email.trim(), password);
        await completeLogin(token, user);
      } else if (mode === "code") {
        const { token, user } = await loginWithEmailCode(email.trim(), code.trim());
        await completeLogin(token, user);
      } else {
        await resetPasswordWithEmailCode(email.trim(), code.trim(), newPassword);
        toast.success("密码已重置，请使用新密码登录");
        setPassword("");
        setCode("");
        setNewPassword("");
        switchMode("password");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  const inputCls =
    "w-full px-4 py-3 bg-surface-container-low border border-outline-variant rounded-lg text-sm text-on-surface placeholder:text-on-surface-variant/50 caret-primary focus:ring-2 focus:ring-primary/60 focus:border-transparent outline-none transition-all";
  const sendBtnDisabled = loading || countdown > 0 || !email.trim();

  return (
    <div className="theme-dark min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 text-primary font-semibold text-2xl mb-2 tracking-tight">
            <BrainCircuit className="h-8 w-8" />
            <span>{APP_NAME}</span>
          </div>
          <p className="text-sm text-on-surface-variant">{APP_TAGLINE}</p>
        </div>

        {/* Login card */}
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant p-8">
          {mode === "reset" ? (
            <>
              <h1 className="text-lg font-semibold text-on-surface mb-6 text-center">
                重置密码
              </h1>
              <button
                onClick={() => switchMode("password")}
                className="mb-4 inline-flex items-center gap-1.5 text-xs text-on-surface-variant hover:text-on-surface transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                返回登录
              </button>
            </>
          ) : (
            <>
              {/* Mode tabs */}
              <div className="flex bg-surface-container-low rounded-lg p-1 mb-6">
                {(
                  [
                    ["password", "密码登录"],
                    ["code", "验证码登录"],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    onClick={() => switchMode(value)}
                    className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                      mode === value
                        ? "bg-surface-container-highest text-on-surface"
                        : "text-on-surface-variant hover:text-on-surface"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-on-surface-variant">
                邮箱
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className={inputCls}
                disabled={loading}
                autoComplete="email"
              />
            </div>

            {mode === "password" && (
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-sm font-medium text-on-surface-variant">
                    密码
                  </label>
                  <button
                    type="button"
                    onClick={() => switchMode("reset")}
                    className="text-xs text-primary hover:underline"
                  >
                    忘记密码？
                  </button>
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="输入密码"
                  className={inputCls}
                  disabled={loading}
                  autoComplete="current-password"
                  autoFocus
                />
              </div>
            )}

            {mode !== "password" && (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    邮箱验证码
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={code}
                      onChange={(e) =>
                        setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                      }
                      placeholder="6 位验证码"
                      className={`${inputCls} font-mono tracking-[0.3em]`}
                      disabled={loading}
                      inputMode="numeric"
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={handleSendCode}
                      disabled={sendBtnDisabled}
                      className="shrink-0 inline-flex items-center gap-1.5 bg-surface-container-low text-on-surface border border-outline-variant px-4 rounded-lg text-sm font-medium hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <Mail className="h-4 w-4" />
                      {countdown > 0 ? `${countdown}s` : "发送验证码"}
                    </button>
                  </div>
                </div>

                {/* Mock-provider dev code — lets internal users finish the flow
                    before SMTP is configured in admin settings. */}
                {devCode && (
                  <div className="text-xs text-on-surface-variant bg-surface-container-low border border-outline-variant rounded-lg px-3 py-2 flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                    邮件服务未配置（mock 模式），本次验证码：
                    <span className="font-mono text-primary">{devCode}</span>
                  </div>
                )}
              </>
            )}

            {mode === "reset" && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  新密码
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="至少 6 位"
                  className={inputCls}
                  disabled={loading}
                  autoComplete="new-password"
                />
              </div>
            )}

            {error && (
              <p className="text-sm text-error bg-error-container/30 border border-error/30 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-on-primary py-3 rounded-lg font-medium hover:bg-primary-container active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogIn className="h-4 w-4" />
              )}
              {loading
                ? "处理中…"
                : mode === "reset"
                  ? "重置密码"
                  : "登录"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-outline mt-6">
          © {new Date().getFullYear()} {APP_FULL_NAME} · 多 Agent 协作工作台
        </p>
      </div>
    </div>
  );
}
