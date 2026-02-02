import React from 'react';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';

/**
 * Renders one math segment with fallback to raw text on KaTeX error
 */
function SafeMath({ type, content, index }) {
    const trimmed = (content || '').trim();
    if (!trimmed) {
        return <span key={index}>{content}</span>;
    }
    const commonProps = {
        math: trimmed,
        errorColor: '#f87171',
        renderError: () => <span className="text-gray-300 font-mono text-sm">{trimmed}</span>,
    };
    if (type === 'block') {
        return (
            <span key={index} className="block my-2">
                <BlockMath {...commonProps} />
            </span>
        );
    }
    return <InlineMath key={index} {...commonProps} />;
}

/**
 * LatexRenderer - Automatically detects and renders LaTeX in text
 *
 * Supports:
 * - ```latex ... ``` and ``` ... ``` (code blocks → block math)
 * - Block math: $$...$$ or \[...\]
 * - Inline math: $...$ or \(...\)
 * - Invalid LaTeX falls back to raw text.
 */
/**
 * Preprocess: normalize LaTeX delimiters so block math is always $$...$$
 * - ```latex ... ``` and ``` ... ``` -> $$...$$
 * - \[ ... \] -> $$...$$ (so \[ \begin{pmatrix}...\end{pmatrix} \] renders)
 */
function preprocessCodeBlocks(text) {
    let out = text;
    out = out.replace(/```(?:latex)?\s*\n([\s\S]*?)```/g, (_, inner) => '$$' + inner.trim() + '$$');
    out = out.replace(/\\\[([\s\S]*?)\\\]/g, (_, inner) => '$$' + inner.trim() + '$$');
    return out;
}

function LatexRenderer({ text, className = '' }) {
    if (!text) return null;

    const normalized = preprocessCodeBlocks(text);
    const segments = parseLatex(normalized);

    return (
        <span className={className}>
            {segments.map((segment, index) => {
                if (segment.type === 'block' || segment.type === 'inline') {
                    return (
                        <SafeMath
                            key={index}
                            type={segment.type}
                            content={segment.content}
                            index={index}
                        />
                    );
                }
                return (
                    <span key={index} className="whitespace-pre-wrap">
                        {segment.content}
                    </span>
                );
            })}
        </span>
    );
}

/**
 * Parse text to extract LaTeX segments
 * Returns array of { type: 'text' | 'inline' | 'block', content: string }
 */
function parseLatex(text) {
    const segments = [];
    let remaining = text;

    // Combined regex to match all LaTeX delimiters
    // Order matters: check block math ($$) before inline ($)
    const patterns = [
        { regex: /\$\$([\s\S]*?)\$\$/g, type: 'block' },      // $$...$$
        { regex: /\\\[([\s\S]*?)\\\]/g, type: 'block' },      // \[...\]
        { regex: /\$([^\$\n]+?)\$/g, type: 'inline' },        // $...$
        { regex: /\\\(([\s\S]*?)\\\)/g, type: 'inline' },     // \(...\)
    ];

    // Process text character by character to handle nested/overlapping patterns
    let pos = 0;
    const len = text.length;

    while (pos < len) {
        let matched = false;
        let earliestMatch = null;
        let earliestType = null;
        let earliestEnd = len;

        // Find the earliest match from current position
        for (const { regex, type } of patterns) {
            regex.lastIndex = pos;
            const match = regex.exec(text);
            if (match && match.index < earliestEnd) {
                earliestMatch = match;
                earliestType = type;
                earliestEnd = match.index;
            }
        }

        if (earliestMatch) {
            // Add text before the match
            if (earliestMatch.index > pos) {
                segments.push({
                    type: 'text',
                    content: text.slice(pos, earliestMatch.index)
                });
            }

            // Add the LaTeX segment
            segments.push({
                type: earliestType,
                content: earliestMatch[1].trim()
            });

            pos = earliestMatch.index + earliestMatch[0].length;
            matched = true;
        }

        if (!matched) {
            // No more matches, add remaining text
            segments.push({
                type: 'text',
                content: text.slice(pos)
            });
            break;
        }
    }

    return segments;
}

/**
 * Simple component for rendering just math (no auto-detection)
 */
export function MathBlock({ math, inline = false }) {
    if (!math) return null;
    
    try {
        return inline 
            ? <InlineMath math={math} errorColor="#f87171" />
            : <BlockMath math={math} errorColor="#f87171" />;
    } catch (e) {
        console.error('LaTeX render error:', e);
        return <span className="text-red-400 font-mono">{math}</span>;
    }
}

/**
 * Check if text contains LaTeX
 */
export function containsLatex(text) {
    if (!text) return false;
    return (/```(?:latex)?\s*\n[\s\S]*?```/.test(text)) ||
        /\\\[[\s\S]*?\\\]/.test(text) ||
        /\$[\s\S]+?\$|\\\([\s\S]+?\\\)/.test(text);
}

export default LatexRenderer;
