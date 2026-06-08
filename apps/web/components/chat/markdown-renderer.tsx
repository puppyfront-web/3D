"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  content: string;
}

/**
 * Renders Markdown content with proper styling for chat messages.
 * Handles headers, bold, lists, code blocks, inline code, links.
 */
export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  if (!content) return null;

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className="text-base font-bold text-[#1A1A2E] mt-3 mb-1.5">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-sm font-bold text-[#1A1A2E] mt-3 mb-1">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-sm font-semibold text-[#1A1A2E] mt-2 mb-1">{children}</h3>
        ),
        p: ({ children }) => (
          <p className="text-sm text-gray-700 leading-relaxed mb-1.5 last:mb-0">{children}</p>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold text-[#1A1A2E]">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic text-gray-600">{children}</em>
        ),
        ul: ({ children }) => (
          <ul className="text-sm text-gray-700 list-disc list-outside ml-4 space-y-0.5 mb-1.5">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="text-sm text-gray-700 list-decimal list-outside ml-4 space-y-0.5 mb-1.5">{children}</ol>
        ),
        li: ({ children }) => (
          <li className="text-sm leading-relaxed">{children}</li>
        ),
        code: ({ className, children }) => {
          // Check if it's a code block (has language class) or inline code
          const isBlock = className?.includes("language-");
          if (isBlock) {
            return (
              <code className="block bg-gray-900 text-gray-100 rounded-lg p-3 text-xs font-mono overflow-x-auto my-2">
                {children}
              </code>
            );
          }
          return (
            <code className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-xs font-mono">
              {children}
            </code>
          );
        },
        pre: ({ children }) => (
          <pre className="bg-gray-900 rounded-lg p-3 overflow-x-auto my-2 text-xs font-mono text-gray-100">
            {children}
          </pre>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#1E3A5F] underline hover:text-[#2D5A8E]"
          >
            {children}
          </a>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-3 border-[#1E3A5F]/30 pl-3 my-2 text-sm text-gray-600 italic">
            {children}
          </blockquote>
        ),
        hr: () => <hr className="border-gray-200 my-3" />,
        table: ({ children }) => (
          <div className="overflow-x-auto my-2">
            <table className="text-xs border border-gray-200 rounded">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="bg-gray-50 px-3 py-1.5 text-left font-medium text-gray-600 border-b border-gray-200">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-1.5 text-gray-700 border-b border-gray-100">{children}</td>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
