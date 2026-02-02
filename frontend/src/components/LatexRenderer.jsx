import React from 'react';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';

/**
 * LatexRenderer - Automatically detects and renders LaTeX in text
 * 
 * Supports:
 * - Inline math: $...$ or \(...\)
 * - Block math: $$...$$ or \[...\]
 * - Mixed text with LaTeX
 * 
 * Usage:
 *   <LatexRenderer text="Solve $x^2 + 2x + 1 = 0$" />
 *   <LatexRenderer text="The answer is $$\int_0^1 x^2 dx = \frac{1}{3}$$" />
 */
function LatexRenderer({ text, className = '' }) {
    if (!text) return null;

    // Parse text and split into segments (plain text and LaTeX)
    const segments = parseLatex(text);

    return (
        <span className={className}>
            {segments.map((segment, index) => {
                if (segment.type === 'block') {
                    return (
                        <span key={index} className="block my-2">
                            <BlockMath math={segment.content} errorColor="#f87171" />
                        </span>
                    );
                } else if (segment.type === 'inline') {
                    return (
                        <InlineMath key={index} math={segment.content} errorColor="#f87171" />
                    );
                } else {
                    return <span key={index}>{segment.content}</span>;
                }
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
    return /\$[\s\S]+?\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]/.test(text);
}

export default LatexRenderer;
