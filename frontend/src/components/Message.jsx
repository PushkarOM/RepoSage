import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import "katex/dist/katex.min.css";

/**
 * Streaming is split from final render on purpose.
 *
 * While the model is streaming, the text is rendered as PLAIN TEXT inside a
 * `whitespace-pre-wrap` span. There is no markdown parsing, no link detection,
 * no inline-code highlighting, no syntax-highlighter component — those all
 * involve non-trivial work per render, and a streaming response triggers a
 * re-render on every word. That re-render cost is what made the per-character
 * typewriter stall: after ~4–5 lines the ReactMarkdown pass took longer than
 * the 16ms tick, so the queue backed up and the rest of the text appeared all
 * at once.
 *
 * When the stream ends, we swap to the full ReactMarkdown render once. The
 * user gets smooth typing during streaming, rich formatting at the end. Same
 * pattern ChatGPT, Claude, and most production chat UIs use.
 */
const WORD_TICK_MS = 45;            // ~22 words/sec
const LONG_WORD_THRESHOLD = 40;     // a "word" longer than this is char-split

function Message({ who, text, streaming = false }) {
  const isUser = who === "you";
  const prefix = isUser ? ">" : "$";
  const prefixClass = isUser ? "text-accent" : "text-success";

  // ---- Typewriter state (only meaningful while streaming) ----
  const [displayedText, setDisplayedText] = useState(
    isUser ? text : ""
  );
  const pendingRef = useRef("");          // chars waiting to be animated
  const processedLength = useRef(isUser ? text.length : 0);

  // When the streamed text grows, push the new suffix into the pending queue.
  // The animation effect below drains the queue.
  useEffect(() => {
    if (isUser) {
      // User bubbles always render fully-formed.
      setDisplayedText(text);
      return;
    }
    const newPart = text.slice(processedLength.current);
    if (newPart.length > 0) {
      pendingRef.current += newPart;
      processedLength.current = text.length;
    }
  }, [text, isUser]);

  // Word-level drain: pop the next whitespace-delimited token from the queue
  // and append it. A token longer than LONG_WORD_THRESHOLD is split into
  // smaller chunks so the longest single token (a code block, a long URL)
  // doesn't appear all at once.
  useEffect(() => {
    if (isUser || !streaming) return undefined;

    const id = setInterval(() => {
      if (pendingRef.current.length === 0) return;

      // Take any leading whitespace first so spacing is preserved exactly
      // (newlines, multiple spaces, etc.).
      const wsMatch = pendingRef.current.match(/^\s+/);
      let slice;
      if (wsMatch) {
        slice = wsMatch[0];
      } else {
        // Next non-whitespace run.
        const wordMatch = pendingRef.current.match(/^\S+/);
        if (!wordMatch) return;
        const word = wordMatch[0];
        if (word.length > LONG_WORD_THRESHOLD) {
          // Split very long tokens into smaller chunks so they animate too.
          slice = word.slice(0, Math.ceil(word.length / 4));
        } else {
          slice = word;
        }
      }

      pendingRef.current = pendingRef.current.slice(slice.length);
      setDisplayedText((prev) => prev + slice);
    }, WORD_TICK_MS);

    return () => clearInterval(id);
  }, [streaming, isUser]);

  // Stream finished: flush anything still pending and show the final text.
  useEffect(() => {
    if (!streaming && !isUser) {
      setDisplayedText(text);
      pendingRef.current = "";
      processedLength.current = text.length;
    }
  }, [streaming, text, isUser]);

  const emptyAgentBubble = streaming && !isUser && displayedText.length === 0;
  const showCursor = streaming && !isUser && pendingRef.current.length > 0;

  // ---- Render: plain text while streaming, full markdown at the end ----
  const body = streaming && !isUser ? (
    // No markdown parser in the hot path. `whitespace-pre-wrap` keeps
    // newlines and runs of spaces; CSS handles the prose-chat typography
    // via the wrapper classes below. Wrap any LaTeX spans in inline-code
    // styling so the math is at least readable (it renders as proper math
    // when the stream ends and we swap to ReactMarkdown below).
    <div className="text-sm text-ink leading-relaxed prose-chat flex-1 min-w-0 break-words whitespace-pre-wrap">
      {displayedText}
      {showCursor && (
        <span className="cursor-blink text-accent" aria-hidden="true">▊</span>
      )}
    </div>
  ) : (
    <div className="text-sm text-ink leading-relaxed prose-chat flex-1 min-w-0 break-words">
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            return !inline && match ? (
              <SyntaxHighlighter
                style={vscDarkPlus}
                language={match[1]}
                PreTag="div"
                customStyle={{ borderRadius: "8px", fontSize: "13px", margin: "8px 0" }}
              >
                {String(children).replace(/\n$/, "")}
              </SyntaxHighlighter>
            ) : (
              <code className="text-accent" {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {displayedText}
      </ReactMarkdown>
    </div>
  );

  return (
    <div className="flex gap-2 min-w-0">
      <span
        className={`font-mono text-sm shrink-0 ${prefixClass} ${emptyAgentBubble ? "loading-breathe" : ""}`}
        aria-hidden="true"
      >
        {prefix}
      </span>
      {body}
    </div>
  );
}

export default Message;