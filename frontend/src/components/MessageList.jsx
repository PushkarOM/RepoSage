import { useEffect, useRef } from "react";
import Message from "./Message";

function MessageList({ messages, loadingHistory }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loadingHistory]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
      {loadingHistory && (
        <p className="font-mono text-sm text-muted loading-breathe">loading conversation...</p>
      )}
      {!loadingHistory && messages.length === 0 && (
        <p className="font-mono text-sm text-muted">// repo ingested — ask about implementation, structure, or good-first-issues</p>
      )}
      {messages.map((m, i) => (
        <Message key={i} who={m.who} text={m.text} />
      ))}
      <div ref={endRef} />
    </div>
  );
}

export default MessageList;