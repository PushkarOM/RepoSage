import { useEffect, useRef, useState, useCallback } from "react";
import Message from "./Message";

const STICK_THRESHOLD = 80; // px from bottom that counts as "pinned"

function MessageList({ messages, loadingHistory, streamingIndex = -1, historyError = "" }) {
  const scrollRef = useRef(null);   // the scrollable viewport (overflow-y-auto, fixed size)
  const contentRef = useRef(null);  // inner wrapper that actually grows as messages print
  const endRef = useRef(null);
  const [pinned, setPinned] = useState(true);
  const pinnedRef = useRef(true);   // mirror of `pinned`, read inside the ResizeObserver callback
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);

  // Track whether the user is at (or near) the bottom of the scroll container.
  // They "unpin" by scrolling up to read history; only the user can flip this,
  // never a re-render.
  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const isPinned = distanceFromBottom <= STICK_THRESHOLD;
    pinnedRef.current = isPinned;
    setPinned(isPinned);
    setShowJumpToLatest(!isPinned);
  }, []);

  // WHY A RESIZE OBSERVER (not a render-keyed effect):
  // The typewriter in Message.jsx drains `displayedText` through its OWN
  // local state, ticking every ~45ms. That state lives inside Message, so
  // updating it does NOT cause MessageList to re-render — React state
  // changes don't propagate upward. An effect here that runs "on every
  // render" therefore only fires once per server chunk (when `messages` or
  // `streamingIndex` actually changes), not once per typewriter tick — so
  // the view jumps in bursts instead of following the cursor smoothly.
  //
  // A ResizeObserver sidesteps React entirely: it watches the real DOM
  // node's box size and fires on every layout change, no matter which
  // component's state triggered it. That's the one thing that's actually
  // in sync with what the user sees growing on screen.
  useEffect(() => {
    const contentEl = contentRef.current;
    if (!contentEl) return undefined;

    const observer = new ResizeObserver(() => {
      if (!pinnedRef.current) return;
      const el = scrollRef.current;
      if (!el) return;
      // Direct assignment, not smooth scroll: this can fire dozens of
      // times a second while typing, and stacking smooth-scroll animations
      // causes visible stutter. An instant jump each tick reads as smooth
      // because the ticks themselves are already small and frequent.
      el.scrollTop = el.scrollHeight;
    });

    observer.observe(contentEl);
    return () => observer.disconnect();
  }, []);

  function jumpToLatest() {
    pinnedRef.current = true;
    setPinned(true);
    setShowJumpToLatest(false);
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  return (
    <div
      ref={scrollRef}
      onScroll={onScroll}
      className="relative flex-1 overflow-y-auto py-4 min-h-0 scrollbar-thin"
    >
      {/* contentRef wraps everything that can change height — this is what
          the ResizeObserver watches. Keeping space-y-4 here (moved down
          from the scroll container) preserves the original spacing. */}
      <div ref={contentRef} className="space-y-4">
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
          <Message key={m.id ?? i} who={m.who} text={m.text} streaming={i === streamingIndex} />
        ))}
        <div ref={endRef} />
      </div>

      {showJumpToLatest && (
        <button
          type="button"
          onClick={jumpToLatest}
          aria-label="Jump to latest message"
          className="sticky bottom-3 left-1/2 -translate-x-1/2 mx-auto block font-mono text-xs text-ink bg-elevated border border-rule rounded-full px-3 py-1.5 shadow-md hover:border-accent hover:text-accent cursor-pointer transition focus:outline-none focus:ring-2 focus:ring-accent-strong"
        >
          ↓ jump to latest
        </button>
      )}
    </div>
  );
}

export default MessageList;
