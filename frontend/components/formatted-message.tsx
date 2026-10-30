"use client"

import React from "react"
import ReactMarkdown from "react-markdown"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"

interface FormattedMessageProps {
  content: string
}

export function FormattedMessage({ content }: FormattedMessageProps) {
  return (
    <div className="prose prose-invert max-w-none text-foreground text-sm leading-relaxed space-y-3">
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          h1: ({ children }) => <h1 className="text-xl font-bold text-primary mt-4 mb-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-semibold text-foreground mt-3 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-semibold text-foreground/90 mt-2 mb-1">{children}</h3>,
          p: ({ children }) => <p className="mb-2 text-foreground/90 leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-2 text-foreground/90">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-2 text-foreground/90">{children}</ol>,
          li: ({ children }) => <li className="text-foreground/90">{children}</li>,
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || "")
            return match ? (
              <pre className="bg-black/50 p-3 rounded-lg border border-border/40 overflow-x-auto text-xs font-mono text-cyan-300 my-2">
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            ) : (
              <code className="bg-secondary/60 text-primary px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
                {children}
              </code>
            )
          },
          table: ({ children }) => (
            <div className="overflow-x-auto my-4 border border-border/40 rounded-lg bg-black/30">
              <table className="min-w-full divide-y divide-border/30 text-xs text-left">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-secondary/40 text-foreground font-semibold">{children}</thead>,
          th: ({ children }) => <th className="px-3 py-2 border-b border-border/30 font-semibold text-foreground/90">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 border-b border-border/20 text-foreground/80">{children}</td>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-primary/70 pl-4 py-1 italic bg-primary/5 rounded-r my-2 text-foreground/80">
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
