import { useEffect, useRef, useState, useCallback, useLayoutEffect } from "react";
import Message from "./Message";

const STICK_THRESHOLD = 80; // px from bottom that counts as "pinned"

function MessageList({ messages, loadingHistory, streamingIndex = -1, historyError = "" }) {
  const scrollRef = useRef(null);
  const endRef = useRef(null);
  const [pinned, setPinned] = useState(true);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);

  // Track whether the user is at (or near) the bottom of the scroll container.
  // They "unpin" by scrolling up to read history; only the user can flip this,
  // never a re-render.
  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const isPinned = distanceFromBottom <= STICK_THRESHOLD;
    setPinned(isPinned);
    setShowJumpToLatest(!isPinned);
  }, []);

  // CRITICAL: the typewriter drains `displayedText` inside the Message
  // component. The parent's `messages` array does NOT change during that
  // drain, so an effect keyed on `messages` only fires when a new chunk
  // arrives from the server. Between chunks, the typewriter is still
  // growing the bubble character-by-character — and the view needs to
  // follow that growth to give a "follow the cursor" feel.
  //
  // useLayoutEffect runs synchronously after every render (before paint),
  // so on every typewriter-driven re-render we can scroll the bottom into
  // view if the user is pinned. `behavior: "auto"` is instant (not animated)
  // — smooth scroll lags too much behind rapid character appends.
  useLayoutEffect(() => {
    if (!pinned) return;
    const el = scrollRef.current;
    const target = endRef.current;
    if (!el || !target) return;
    // Scroll the bottom anchor into view at the bottom of the container.
    target.scrollIntoView({ behavior: "auto", block: "end" });
  });

  function jumpToLatest() {
    setPinned(true);
    setShowJumpToLatest(false);
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  return (
    <div
      ref={scrollRef}
      onScroll={onScroll}
      className="relative flex-1 overflow-y-auto px-6 py-4 space-y-4 min-h-0"
    >
      {loadingHistory && (
        <p className="font-mono text-sm text-muted loading-breathe">loading conversation...</p>
      )}
      {historyError && (
        <p role="alert" aria-live="polite" className="font-mono text-sm text-danger">
          // could not load history: {historyError}
        </p>
      )}
      {!loadingHistory && !historyError && messages.length === 0 && (
        <p className="font-mono text-sm text-muted">// repo ingested — ask about implementation, structure, or good-first-issues</p>
      )}
      {messages.map((m, i) => (
        <Message key={i} who={m.who} text={m.text} streaming={i === streamingIndex} />
      ))}
      <div ref={endRef} />

      {showJumpToLatest && (
        <button
          type="button"
          onClick={jumpToLatest}
          aria-label="Jump to latest message"
          className="sticky bottom-3 left-1/2 -translate-x-1/2 mx-auto block font-mono text-xs text-ink bg-elevated border border-rule rounded-full px-3 py-1.5 shadow-md hover:border-accent hover:text-accent transition focus:outline-none focus:ring-2 focus:ring-accent-strong"
        >
          ↓ jump to latest
        </button>
      )}
    </div>
  );
}

export default MessageList;