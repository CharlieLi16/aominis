import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

/**
 * If GPT (or API) returns content wrapped in ```markdown ... ``` or ``` ... ```,
 * unwrap so the inner content is rendered as markdown instead of a code block.
 */
function unwrapMarkdownCodeBlock(md) {
    const trimmed = md.trim();
    const match = trimmed.match(/^```(?:markdown)?\s*\n?([\s\S]*?)\n?```\s*$/);
    return match ? match[1].trim() : md;
}

/**
 * Renders Markdown with optional math: $...$ and $$...$$ via KaTeX.
 * Supports GFM: lists, tables, bold, italic, code, etc.
 */
function MarkdownRenderer({ text, className = '' }) {
    if (!text) return null;
    const content = unwrapMarkdownCodeBlock(text);

    return (
        <div className={`markdown-body ${className}`}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                    p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                    ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-2 space-y-0.5" {...props} />,
                    ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-2 space-y-0.5" {...props} />,
                    h1: ({ node, ...props }) => <h1 className="text-lg font-bold mb-2 mt-3" {...props} />,
                    h2: ({ node, ...props }) => <h2 className="text-base font-bold mb-1.5 mt-2" {...props} />,
                    code: ({ node, inline, ...props }) =>
                        inline ? (
                            <code className="bg-dark-700 px-1 rounded text-sm" {...props} />
                        ) : (
                            <code className="block bg-dark-700 p-2 rounded text-sm overflow-x-auto" {...props} />
                        ),
                    pre: ({ node, ...props }) => <pre className="mb-2 overflow-x-auto" {...props} />,
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}

export default MarkdownRenderer;
