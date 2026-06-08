"use client";

interface TextBlockProps {
  content: string;
}

export function TextBlock({ content }: TextBlockProps) {
  if (!content) return null;
  return <p className="text-sm text-gray-700">{content}</p>;
}
