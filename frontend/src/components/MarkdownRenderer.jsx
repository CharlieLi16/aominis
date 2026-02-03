import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import katex from 'katex';
import 'katex/dist/katex.min.css';

/**
 * If GPT returns content wrapped in ```markdown ... ```, unwrap it.
 */
function unwrapMarkdownCodeBlock(md) {
    const trimmed = md.trim();
    const match = trimmed.match(/^```(?:markdown)?\s*\n?([\s\S]*?)\n?```\s*$/);
    return match ? match[1].trim() : md;
}

/**
 * Render a LaTeX expression using KaTeX.
 * Returns HTML string or error message.
 */
function renderLatex(latex, displayMode) {
    try {
        return katex.renderToString(latex, {
            displayMode,
            throwOnError: false,
            strict: false,
        });
    } catch (e) {
        console.error('KaTeX error:', e);
        return `<span class="text-red-400">[Math Error: ${e.message}]</span>`;
    }
}

/**
 * Process text to render all math expressions with KaTeX directly.
 * Supports: \[...\], \(...\), $$...$$, $...$
 * 
 * This approach is similar to how ChatGPT renders math - 
 * KaTeX processes math expressions directly, not through remark-math.
 */
function processLatex(text) {
    if (!text) return { segments: [], hasLatex: false };
    
    const segments = [];
    let lastIndex = 0;
    let hasLatex = false;
    
    // Combined regex for all math delimiters
    // Order matters: longer/display patterns first
    // \[...\] - display math (LaTeX style)
    // $$...$$ - display math (TeX style)  
    // \(...\) - inline math (LaTeX style)
    // $...$ - inline math (TeX style) - but not \$ escaped
    const mathRegex = /\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$|\\\(([\s\S]*?)\\\)|(?<!\\\$)\$(?!\$)((?:[^$\\]|\\.)+?)\$/g;
    
    let match;
    while ((match = mathRegex.exec(text)) !== null) {
        // Add text before this match
        if (match.index > lastIndex) {
            segments.push({
                type: 'text',
                content: text.slice(lastIndex, match.index)
            });
        }
        
        // Determine which group matched
        let latex, displayMode;
        if (match[1] !== undefined) {
            // \[...\] - display
            latex = match[1];
            displayMode = true;
        } else if (match[2] !== undefined) {
            // $$...$$ - display
            latex = match[2];
            displayMode = true;
        } else if (match[3] !== undefined) {
            // \(...\) - inline
            latex = match[3];
            displayMode = false;
        } else if (match[4] !== undefined) {
            // $...$ - inline
            latex = match[4];
            displayMode = false;
        }
        
        if (latex !== undefined) {
            hasLatex = true;
            segments.push({
                type: 'latex',
                content: latex.trim(),
                displayMode,
                html: renderLatex(latex.trim(), displayMode)
            });
        }
        
        lastIndex = match.index + match[0].length;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
        segments.push({
            type: 'text',
            content: text.slice(lastIndex)
        });
    }
    
    return { segments, hasLatex };
}

/**
 * Component to render a single segment (text or latex)
 */
function Segment({ segment }) {
    if (segment.type === 'latex') {
        // Render KaTeX HTML directly
        const Tag = segment.displayMode ? 'div' : 'span';
        return (
            <Tag
                className={segment.displayMode ? 'my-2 overflow-x-auto' : ''}
                dangerouslySetInnerHTML={{ __html: segment.html }}
            />
        );
    }
    
    // Render text as markdown (without math processing)
    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                p: ({ node, ...props }) => <span {...props} />, // Avoid extra <p> wrapping
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
            {segment.content}
        </ReactMarkdown>
    );
}

/**
 * MarkdownRenderer - Renders Markdown with LaTeX math support.
 * 
 * Uses KaTeX directly (like ChatGPT) instead of remark-math.
 * Supports all common math delimiters:
 *   - \[...\] and $$...$$ for display math
 *   - \(...\) and $...$ for inline math
 */
function MarkdownRenderer({ text, className = '' }) {
    const processed = useMemo(() => {
        if (!text) return { segments: [], hasLatex: false };
        const content = unwrapMarkdownCodeBlock(text);
        return processLatex(content);
    }, [text]);
    
    if (!text) return null;
    
    // If no LaTeX, render as simple markdown
    if (!processed.hasLatex) {
        return (
            <div className={`markdown-body ${className}`}>
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
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
                    {unwrapMarkdownCodeBlock(text)}
                </ReactMarkdown>
            </div>
        );
    }
    
    // Render segments (mixed text and latex)
    return (
        <div className={`markdown-body ${className}`}>
            {processed.segments.map((segment, index) => (
                <Segment key={index} segment={segment} />
            ))}
        </div>
    );
}

export default MarkdownRenderer;
