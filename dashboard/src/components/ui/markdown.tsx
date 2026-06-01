"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

interface MarkdownProps {
  children: string;
  className?: string;
  /** When true, links open in a new tab. Default true (agent output is untrusted-by-default). */
  externalLinks?: boolean;
}

/**
 * Renders agent markdown output with sane defaults for the Rugol dashboard.
 *
 * - GFM: tables, task lists, autolinks.
 * - Syntax highlighting via rehype-highlight (CSS theme is in markdown.css).
 * - Links default to target=_blank rel=noopener noreferrer because content
 *   originates from an LLM and may carry external URLs we did not vet.
 */
export function MarkdownView({ children, className, externalLinks = true }: MarkdownProps) {
  return (
    <div className={`md-view text-[14px] leading-relaxed ${className ?? ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          a: (props) =>
            externalLinks ? (
              <a {...props} target="_blank" rel="noopener noreferrer" />
            ) : (
              <a {...props} />
            ),
          code({ className, children, ...rest }: any) {
            const isInline = !className;
            if (isInline) {
              return (
                <code
                  className="px-1 py-0.5 rounded bg-[--color-bg-elev] text-[--color-accent-strong] font-mono text-[12.5px]"
                  {...rest}
                >
                  {children}
                </code>
              );
            }
            return (
              <code className={className} {...rest}>
                {children}
              </code>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
