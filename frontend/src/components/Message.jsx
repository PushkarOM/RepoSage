import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

function Message({ who, text }) {
  const isUser = who === "you";
  const prefix = isUser ? ">" : "$";
  const prefixClass = isUser ? "text-accent" : "text-success";

  return (
    <div className="flex gap-2">
      <span className={`font-mono text-sm shrink-0 ${prefixClass}`}>{prefix}</span>
      <div className="text-sm text-ink leading-relaxed prose-chat flex-1">
        <ReactMarkdown
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
          {text}
        </ReactMarkdown>
      </div>
    </div>
  );
}

export default Message;