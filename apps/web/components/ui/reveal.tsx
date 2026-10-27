"use client";

// Reveal — dependency-free scroll-in animation (IntersectionObserver).
// Sections fade/slide up once when entering the viewport; respects
// prefers-reduced-motion via motion-reduce variants.

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  /** Stagger delay in ms — useful for card grids. */
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={cn(
        "transition-all duration-700 ease-out",
        visible
          ? "opacity-100 translate-y-0"
          : "opacity-0 translate-y-5 motion-reduce:opacity-100 motion-reduce:translate-y-0",
        className,
      )}
    >
      {children}
    </div>
  );
}
