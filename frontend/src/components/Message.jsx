import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import "katex/dist/katex.min.css";

/**
 * Streaming vs. animating
 * ------------------------
 * `streaming` (prop) = "the network/fetch for this message is still open."
 * `isAnimating` (state) = "the typewriter still has queued characters to show."
 *
 * These are NOT the same clock, and conflating them causes two distinct bugs:
 *
 * 1. If we stop the typewriter the instant `streaming` flips to false, any
 *    reply longer than a few lines gets cut off and dumped in full, because
 *    the network finishes delivering tokens well before the typewriter
 *    (which is throttled to ~22 words/sec) has caught up.
 *
 * 2. If we seed the "already streamed" position at 0 for every assistant
 *    message regardless of `streaming`, then a HISTORICAL message — loaded
 *    on page refresh with `streaming={false}` and its full text already
 *    present — looks to the ingest effect exactly like a brand-new stream
 *    starting from scratch, and it gets typed out too.
 *
 * The fix for both: `isAnimating` is derived state that starts true only
 * when a message mounts WHILE still streaming, and it only turns false once
 * the pending queue is actually empty AND the source has stopped sending.
 * A message that mounts already-complete never enters the animating state
 * at all.
 */
const WORD_TICK_MS = 45;            // ~22 words/sec
const LONG_WORD_THRESHOLD = 40;     // a "word" longer than this is char-split

function Message({ who, text, streaming = false }) {
  const isUser = who === "you";
  const prefix = isUser ? ">" : "$";
  const prefixClass = isUser ? "text-accent" : "text-success";

  // ---- Initial state depends on whether this message is ALREADY finished
  // at mount time, not just on whether it's from the assistant. ----
  const [displayedText, setDisplayedText] = useState(() => {
    if (isUser) return text;
    // Historical / already-complete assistant message: render it fully
    // formed immediately, don't feed it through the typewriter.
    return streaming ? "" : text;
  });

  const [isAnimating, setIsAnimating] = useState(!isUser && streaming);

  const pendingRef = useRef("");                 // chars waiting to be animated
  const processedLength = useRef(
    isUser ? text.length : (streaming ? 0 : text.length)
  );

  // Ingest: when the streamed text grows, push the new suffix into the
  // pending queue. For a message that mounted already-complete, this is a
  // no-op forever (processedLength already equals text.length).
  useEffect(() => {
    if (isUser) {
      setDisplayedText(text);
      return;
    }
    const newPart = text.slice(processedLength.current);
    if (newPart.length > 0) {
      pendingRef.current += newPart;
      processedLength.current = text.length;
      setIsAnimating(true); // (re)start the drain loop if it wasn't running
    }
  }, [text, isUser]);

  // Drain loop: pop the next whitespace-delimited token from the queue and
  // append it. Keeps running as long as there's queued content — it does
  // NOT stop just because `streaming` went false; it stops only once the
  // queue is empty AND the source has finished sending.
  useEffect(() => {
    if (isUser || !isAnimating) return undefined;

    const id = setInterval(() => {
      if (pendingRef.current.length === 0) {
        if (!streaming) setIsAnimating(false); // genuinely done
        return; // otherwise: idle, waiting for more streamed tokens
      }

      const wsMatch = pendingRef.current.match(/^\s+/);
      let slice;
      if (wsMatch) {
        slice = wsMatch[0];
      } else {
        const wordMatch = pendingRef.current.match(/^\S+/);
        if (!wordMatch) return;
        const word = wordMatch[0];
        slice = word.length > LONG_WORD_THRESHOLD
          ? word.slice(0, Math.ceil(word.length / 4))
          : word;
      }

      pendingRef.current = pendingRef.current.slice(slice.length);
      setDisplayedText((prev) => prev + slice);
    }, WORD_TICK_MS);

    return () => clearInterval(id);
  }, [isAnimating, isUser, streaming]);

  const emptyAgentBubble = isAnimating && !isUser && displayedText.length === 0;
  const showCursor = isAnimating && !isUser && pendingRef.current.length > 0;

  // ---- Render: plain text while animating, full markdown once settled ----
  // NOTE ON THE `key` PROPS: both branches render a <div> at the same tree
  // position. Without distinct keys, React reconciles them as the SAME DOM
  // node — it just mutates its className/children in one commit instead of
  // unmounting/remounting. That silently breaks a fade-in: the node's
  // opacity was implicitly 1 the instant before the swap, so introducing
  // `opacity-0` in the very same commit that introduces the transition
  // makes the browser play a 1→0 transition (fade OUT), immediately
  // followed by our code correcting it back to 1 — a flicker too fast to
  // see, which looks exactly like no animation at all. Giving each branch
  // its own key forces a real unmount/mount, so the markdown view arrives
  // as a genuinely fresh node with no prior opacity to race against.
  const body = !isUser && isAnimating ? (
    <div key="typewriter" className="text-sm text-ink leading-relaxed prose-chat flex-1 min-w-0 break-words whitespace-pre-wrap">
      {displayedText}
      {showCursor && (
        <span className="cursor-blink text-accent" aria-hidden="true">▊</span>
      )}
    </div>
  ) : (
    <div key="markdown" className={`text-sm text-ink leading-relaxed prose-chat flex-1 min-w-0 break-words ${isUser ? "" : "fade-in-markdown"}`}>
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
