"use client";

// Canvas workspace is frozen (KB-QA-Foundation). Legacy URLs redirect to chat.

import { Suspense, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

function CanvasRedirect() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const projectId = params.projectId as string;
    const initPrompt = searchParams.get("init_prompt");
    const target = initPrompt
      ? `/workspace/chat/${projectId}?init_prompt=${encodeURIComponent(initPrompt)}`
      : `/workspace/chat/${projectId}`;
    router.replace(target);
  }, [params.projectId, router, searchParams]);

  return (
    <div className="flex items-center justify-center h-full">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}

export default function CanvasWorkspacePage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <CanvasRedirect />
    </Suspense>
  );
}
