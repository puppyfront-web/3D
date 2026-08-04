"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";

import { ConversationPanel } from "@/components/canvas/conversation-panel";
import { getProjectById } from "@/lib/api";

function ChatWorkspaceContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = params.projectId as string;
  const initialPrompt = searchParams.get("init_prompt") ?? undefined;

  const [projectName, setProjectName] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await getProjectById(projectId);
      if (!cancelled && res.success && res.data) {
        setProjectName(res.data.name);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return (
    <div className="flex flex-col h-full bg-surface">
      <header className="shrink-0 flex items-center gap-4 px-4 py-3 border-b border-outline-variant bg-surface-container-lowest">
        <Link
          href="/workspace/projects"
          className="inline-flex items-center gap-1.5 text-sm text-on-surface-variant hover:text-primary transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          返回项目
        </Link>
        <div className="h-4 w-px bg-outline-variant" />
        <div className="min-w-0">
          <h1 className="text-sm font-semibold text-on-surface truncate">
            {projectName || "知识问答"}
          </h1>
          <p className="text-xs text-on-surface-variant">
            基于项目资料与内部知识库回答，请核对引用来源
          </p>
        </div>
      </header>

      <div className="flex-1 min-h-0">
        <ConversationPanel
          projectId={projectId}
          initialPrompt={initialPrompt}
          layout="page"
        />
      </div>
    </div>
  );
}

export default function ChatWorkspacePage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <ChatWorkspaceContent />
    </Suspense>
  );
}
