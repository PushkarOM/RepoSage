import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import PromptBar from "../components/PromptBar";
import ThemeToggle from "../components/ThemeToggle";
import LogoutButton from "../components/LogoutButton";
import { REPO, TAGLINE, PORTFOLIO, CONTACT } from "@/lib/copy";

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
    <div>
      <p className="font-mono text-xs text-muted mb-2">
        // example conversation — click login to try it yourself
      </p>
      <div className="w-full bg-elevated border border-rule rounded-lg shadow-2xl overflow-hidden">
        <div className="flex items-center gap-1.5 px-4 py-3 border-b border-rule">
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
    </div>
  );
}

const HOW_IT_WORKS = [
  {
    label: "$ ingest <url>",
    body: "Clone, chunk, and embed any public or private repo — code and docs indexed separately.",
  },
  {
    label: "> ask anything",
    body: 'Architecture, implementation details, "where do I even start" — grounded in the real code, with citations.',
  },
  {
    label: "$ good-first-issues",
    body: "Get pointed to real issues you can fix, not a generic contribution guide.",
  },
];

function ContributeSection() {
  const [repoStats, setRepoStats] = useState(null);
  const [issues, setIssues] = useState(null);
  const [issuesError, setIssuesError] = useState(false);

  useEffect(() => {
    fetch(`https://api.github.com/repos/${REPO}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => setRepoStats({ stars: data.stargazers_count, forks: data.forks_count }))
      .catch(() => {});

    fetch(`https://api.github.com/repos/${REPO}/issues?labels=good%20first%20issue&state=open&per_page=5`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setIssues)
      .catch(() => setIssuesError(true));
  }, []);

  const showStats = repoStats && (repoStats.stars > 0 || repoStats.forks > 0);

  return (
    <>
      <p className="font-mono text-xs text-success mb-3">
        <span className="text-success">$</span> contribute
      </p>
      <p className="text-base text-ink mb-1">
        RepoSage is open source{showStats && (
          <span className="text-muted"> — {repoStats.stars} stars, {repoStats.forks} forks</span>
        )}
      </p>
      <p className="text-base text-muted mb-8 max-w-2xl leading-relaxed">
        Real, currently-open good-first-issues from this repo — pulled live, the same way
        RepoSage's own list_good_first_issues tool would answer this for any repo you ask it about.
      </p>

      {issues === null && !issuesError && (
        <p className="font-mono text-xs text-muted">loading open issues...</p>
      )}

      {issuesError && (
        <p className="text-base text-muted">
          Check current good-first-issues directly on{" "}
          <a
            href={`https://github.com/${REPO}/issues`}
            target="_blank"
            rel="noreferrer"
            className="text-success hover:underline"
          >
            GitHub →
          </a>
        </p>
      )}

      {issues && issues.length === 0 && (
        <p className="text-base text-muted">
          No open good-first-issues right now — check back soon, or{" "}
          <a
            href={`https://github.com/${REPO}/issues/new`}
            target="_blank"
            rel="noreferrer"
            className="text-success hover:underline"
          >
            open one yourself
          </a>
          .
        </p>
      )}

      {issues && issues.length > 0 && (
        <div className="space-y-3">
          {issues.map((issue) => (
            <a
              key={issue.id}
              href={issue.html_url}
              target="_blank"
              rel="noreferrer"
              className="block bg-elevated border border-rule rounded-lg px-5 py-4 hover:border-success/50 transition"
            >
              <p className="text-base text-ink">
                <span className="text-success">●</span> #{issue.number} {issue.title}
              </p>
            </a>
          ))}
        </div>
      )}
    </>
  );
}

function Landing() {
  const { isAuthenticated, authChecked } = useAuth();
  const navigate = useNavigate();

  // Reflect the resolved auth state in both the CTA copy and its target:
  //   - logged in         -> "go to dashboard" -> /dashboard
  //   - logged out        -> "login"           -> /login
  //   - still checking    -> "enter"           -> /dashboard (RequireAuth
  //     bounces an unauthed visitor to /login; this keeps the CTA stable
  //     during the silent /refresh so an authed user doesn't see the
  //     label flicker from "login" -> "go to dashboard")
  const cta = !authChecked
    ? "enter"
    : isAuthenticated
      ? "go to dashboard"
      : "login";
  const ctaTarget = !authChecked
    ? "/dashboard"
    : isAuthenticated
      ? "/dashboard"
      : "/login";

  return (
    <div className="bg-paper">
      <section className="px-4 pt-6 pb-20 border-b border-rule">
        <div className="w-full max-w-7xl mx-auto">
          <div className="mt-12 grid md:grid-cols-2 gap-16 items-center">
            {/* Left: copy + CTAs */}
            <div>
              <p className="font-mono text-xs text-muted mb-3">
                <span className="text-accent">$</span> {TAGLINE}
              </p>
              <h1 className="font-display text-5xl sm:text-6xl text-ink tracking-tight leading-[1.05]">
                Chat with any
                <br />
                GitHub repo.
              </h1>
              <p className="mt-5 text-muted text-lg leading-relaxed max-w-md">
                RepoSage clones, indexes, and lets you ask real questions about a codebase —
                then points you toward issues you can actually fix.
              </p>
              <div className="mt-10 flex flex-wrap items-center gap-3">
                <Button size="lg" onClick={() => navigate(ctaTarget)}>{cta}</Button>
                <Button
                  variant="ghost"
                  onClick={() => window.open(`https://github.com/${REPO}`, "_blank", "noreferrer")}
                >
                  view source →
                </Button>
              </div>
            </div>

            {/* Right: the terminal demo, filling its column rather than being width-capped */}
            <div>
              <TerminalDemo />
            </div>
          </div>
        </div>
      </section>

      {/* Marquee banner — single REPOSAGE wordmark, scrolling left to right.
          Two copies of the wordmark are rendered inside the moving track so
          the loop is seamless (see .marquee-track in index.css); the user
          only ever sees one line. */}
      <section aria-hidden="true" className="py-6 select-none overflow-hidden border-y border-rule ">
        <div className="marquee-track flex whitespace-nowrap">
          {[0, 1].map((i) => (
            <span
              key={i}
              className="font-display font-black tracking-[-0.04em] leading-none text-ink shrink-0 pr-16"
              style={{
                fontSize: "clamp(72px, 14vw, 200px)",
                opacity: 0.08,
              }}
            >
              REPOSAGE
            </span>
          ))}
        </div>
      </section>

      {/* How it works band -- elevated, breaks the flat scroll with real value contrast */}
      <section className="bg-elevated border-y border-rule px-4 py-20">
        <div className="w-full max-w-5xl mx-auto">
          <p className="font-mono text-xs text-muted mb-8">
            <span className="text-accent">$</span> how to use it
          </p>
          <div className="grid sm:grid-cols-3 gap-6">
            {HOW_IT_WORKS.map((item) => (
              <div key={item.label} className="bg-paper border border-rule rounded-lg p-6">
                <p className="font-mono text-xs text-accent mb-3">{item.label}</p>
                <p className="text-sm text-muted leading-relaxed">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contribute band */}
      <section className="px-4 py-20">
        <div className="w-full max-w-5xl mx-auto">
          <ContributeSection />
        </div>
      </section>

      <footer className="border-t border-rule px-4 py-8">
        <div className="w-full max-w-7xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-6 items-center">
          {/* Left: wordmark */}
          <span className="font-mono text-xs text-muted/60">reposage</span>

          {/* Middle: quick links — kept as a horizontal row on sm+,
              stacks below the wordmark on mobile. */}
          <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 font-mono text-xs text-muted">
            <span>|</span>
            <a
              href={`https://github.com/${REPO}`}
              target="_blank"
              rel="noreferrer"
              className="hover:text-accent transition"
            >
               github
            </a>
            <span>|</span>
            <a
              href={PORTFOLIO}
              target="_blank"
              rel="noreferrer"
              className="hover:text-accent transition"
            >
              portfolio 
            </a>
            <span>|</span>
            <a
              href={CONTACT}
              target="_blank"
              rel="noreferrer"
              className="hover:text-accent transition"
            >
              contact 
            </a>
            <span>|</span>
          </nav>

          {/* Right: copyright */}
          <p className="font-mono text-xs text-muted/60 sm:text-right">
            © {new Date().getFullYear()} reposage
          </p>
        </div>
      </footer>
    </div>
  );
}

export default Landing;
