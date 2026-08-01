import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import PromptBar from "../components/PromptBar";

const DEMO_LINES = [
  { type: "cmd", text: "$ reposage ingest facebook/react" },
  { type: "status", text: "✓ ingested — 4,218 chunks indexed" },
  { type: "user", text: "> How does the reconciler decide what to re-render?" },
  {
    type: "agent",
    text: "The reconciler walks the fiber tree and diffs each node against its previous version, marking only changed subtrees for commit.",
  },
  { type: "cite", text: "[packages/react-reconciler/src/ReactFiberBeginWork.js]" },
];

// Text color per line type — mapped to the page's theme tokens (ink/muted/accent)
// instead of raw --color-* vars, so this actually re-colors when the theme changes.
const LINE_COLOR = {
  cmd: "text-accent",
  status: "text-accent",
  user: "text-accent",
  agent: "text-ink",
  cite: "text-muted",
};

function TerminalDemo() {
  const [visibleLines, setVisibleLines] = useState(0);
  const [charsInLine, setCharsInLine] = useState(0);
  const reducedMotion = useRef(
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    if (reducedMotion.current) {
      setVisibleLines(DEMO_LINES.length);
      return;
    }
    if (visibleLines >= DEMO_LINES.length) return;

    const currentLine = DEMO_LINES[visibleLines].text;
    if (charsInLine < currentLine.length) {
      const t = setTimeout(() => setCharsInLine((c) => c + 1), 14);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => {
      setVisibleLines((v) => v + 1);
      setCharsInLine(0);
    }, 500);
    return () => clearTimeout(t);
  }, [visibleLines, charsInLine]);

  return (
    <div className="w-full bg-elevated border border-rule rounded-lg shadow-2xl overflow-hidden">
      <div className="flex items-center gap-1.5 px-4 py-3 border-b border-rule">
        {/* Decorative traffic-light dots — intentionally literal red/amber/green,
            not theme tokens, same as macOS window chrome in either theme. */}
        <span className="w-2.5 h-2.5 rounded-full bg-red-500/50" />
        <span className="w-2.5 h-2.5 rounded-full bg-amber-500/50" />
        <span className="w-2.5 h-2.5 rounded-full bg-green-500/50" />
      </div>
      <div className="p-5 space-y-2 min-h-55">
        {DEMO_LINES.slice(0, visibleLines).map((line, i) => (
          <p key={i} className={`font-mono text-sm ${LINE_COLOR[line.type]}`}>
            {line.text}
          </p>
        ))}
        {visibleLines < DEMO_LINES.length && (
          <p className={`font-mono text-sm ${LINE_COLOR[DEMO_LINES[visibleLines].type]}`}>
            {DEMO_LINES[visibleLines].text.slice(0, charsInLine)}
            <span className="animate-pulse">▊</span>
          </p>
        )}
      </div>
    </div>
  );
}

function Landing() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const cta = token ? "go to dashboard" : "login";
  const ctaTarget = token ? "/dashboard" : "/login";

  return (
    <div className="min-h-[calc(100vh-57px)] bg-paper px-4 py-12">
      <div className="w-full max-w-3xl mx-auto">
        <PromptBar />

        <div className="mt-20">
          <p className="font-mono text-xs text-muted mb-3">
            <span className="text-accent">$</span> open-source · agentic RAG
          </p>
          <h1 className="font-display text-5xl sm:text-6xl text-ink tracking-tight leading-[1.05]">
            Chat with any
            <br />
            GitHub repo.
          </h1>
          <p className="mt-6 text-muted text-lg leading-relaxed max-w-xl">
            RepoSage clones, indexes, and lets you ask real questions about a codebase —
            then points you toward issues you can actually fix.
          </p>

          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Button onClick={() => navigate(ctaTarget)}>{cta}</Button>
            <Button
              variant="ghost"
              onClick={() => window.open("https://github.com/PushkarOM/RepoSage", "_blank", "noreferrer")}
            >
              view source →
            </Button>
          </div>

          <div className="mt-10 max-w-xl">
            <TerminalDemo />
          </div>
        </div>

        <div className="mt-20 border-t border-rule pt-8">
          <p className="font-mono text-xs text-muted mb-6">
            <span className="text-accent">$</span> how it works
          </p>
          <div className="grid sm:grid-cols-3 gap-8">
            <div>
              <p className="font-mono text-xs text-accent mb-2">$ ingest &lt;url&gt;</p>
              <p className="text-sm text-muted leading-relaxed">
                Clone, chunk, and embed any public or private repo — code and docs indexed separately.
              </p>
            </div>
            <div>
              <p className="font-mono text-xs text-accent mb-2">&gt; ask anything</p>
              <p className="text-sm text-muted leading-relaxed">
                Architecture, implementation details, "where do I even start" — grounded in the real code, with citations.
              </p>
            </div>
            <div>
              <p className="font-mono text-xs text-accent mb-2">$ contribute</p>
              <p className="text-sm text-muted leading-relaxed">
                Get pointed to real good-first-issues, not a generic contribution guide.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-16 border-t border-rule pt-8">
          <div className="bg-elevated border border-rule rounded-lg px-6 py-8 text-center">
            <p className="font-display text-xl text-ink mb-2">
              Not sure where to start?
            </p>
            <p className="text-sm text-muted max-w-md mx-auto">
              Ask RepoSage about RepoSage. This project is self-hostable and self-explaining —
              ingest its own repo and ask it how it works.
            </p>
          </div>
        </div>

        <footer className="mt-16 border-t border-rule pt-6 flex items-center justify-between">
          <span className="font-mono text-xs text-muted/60">reposage</span>
          <a
            href="https://github.com/PushkarOM/RepoSage"
            target="_blank"
            rel="noreferrer"
            className="font-mono text-xs text-muted hover:text-accent transition"
          >
            github →
          </a>
        </footer>
      </div>
    </div>
  );
}

export default Landing;
