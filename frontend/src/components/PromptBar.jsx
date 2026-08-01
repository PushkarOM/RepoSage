import { useLocation, useParams } from "react-router-dom";

function pageForPath(pathname) {
  if (pathname === "/login") return "auth";
  if (pathname === "/dashboard") return "dashboard";
  if (pathname === "/ingest") return "ingest";
  if (pathname.startsWith("/repos/") && pathname.endsWith("/threads")) return "threads";
  if (pathname.startsWith("/repos/") && pathname.includes("/threads/")) return "chat";
  return "default";
}

function copyFor(page, params, threadTitle) {
  const repoId = params.owner && params.name ? `${params.owner}/${params.name}` : null;
  switch (page) {
    case "auth":      return "";
    case "dashboard": return "your repos";
    case "ingest":    return repoId ? `ingest ${repoId}` : "ingest";
    case "threads":   return repoId ?? "";
    case "chat":      return repoId ? `${repoId} • ${threadTitle ?? "new conversation"}` : "";
    default:          return "";
  }
}

function PromptBar({ threadTitle }) {
  const { pathname } = useLocation();
  const params = useParams();
  const page = pageForPath(pathname);
  const copy = copyFor(page, params, threadTitle);

  return (
    <div className="font-mono text-xs text-muted flex items-center gap-1.5">
      <span className="text-accent">$</span>
      <span>reposage</span>
      {copy && (
        <>
          <span className="text-muted/60">—</span>
          <span>{copy}</span>
        </>
      )}
    </div>
  );
}

export default PromptBar;