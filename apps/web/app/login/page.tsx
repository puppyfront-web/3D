"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { CloudCog, Loader2, LogIn } from "lucide-react";
import { toast } from "sonner";
import { login } from "@/lib/api";
import { setToken, setStoredUser, isAuthenticated } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Already logged in → redirect to workspace
  useEffect(() => {
    if (isAuthenticated()) {
      router.replace("/workspace/projects");
    }
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("请输入邮箱和密码");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { token, user } = await login(email.trim(), password);
      setToken(token);
      setStoredUser({ name: user?.name, email: user?.email });
      toast.success(`欢迎回来，${user?.name || email}`);
      router.replace("/workspace/projects");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 text-primary font-bold text-2xl mb-2">
            <CloudCog className="h-8 w-8" />
            <span>企业知识助手</span>
          </div>
          <p className="text-sm text-on-surface-variant">
            内部知识库与可追溯问答
          </p>
        </div>

        {/* Login card */}
        <div className="bg-surface-container-lowest rounded-xl shadow-lg border border-outline-variant p-8">
          <h1 className="text-lg font-semibold text-on-surface mb-6 text-center">
            登录
          </h1>

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
                className="w-full px-4 py-3 bg-surface-container-low border border-outline-variant rounded-lg text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                disabled={loading}
                autoComplete="email"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-on-surface-variant">
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="输入密码"
                className="w-full px-4 py-3 bg-surface-container-low border border-outline-variant rounded-lg text-sm focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                disabled={loading}
                autoComplete="current-password"
                autoFocus
              />
            </div>

            {error && (
              <p className="text-sm text-error bg-error-container/30 border border-error/30 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-on-primary py-3 rounded-lg font-medium hover:opacity-90 active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogIn className="h-4 w-4" />
              )}
              {loading ? "登录中…" : "登录"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-outline mt-6">
          © {new Date().getFullYear()} 企业知识助手
        </p>
      </div>
    </div>
  );
}
