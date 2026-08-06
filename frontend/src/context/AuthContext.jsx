import { createContext, useCallback, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { logout as logoutApi, refreshTokens } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // The httpOnly cookie IS the credential -- JS can't read it, so we
  // can't keep it in state. Instead we mirror an auth status that's
  // set on /login success and verified by a silent /refresh on app
  // mount (see App.jsx + checkAuth below).
  //
  // `authChecked` becomes true exactly once -- after the initial silent
  // /refresh resolves. Renderers (RequireAuth, LoginGate) use it to
  // decide between "still figuring it out" (return null / spinner) and
  // "show login form" / "show protected page".
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

  // Called on mount. Calls `refreshTokens` (NOT raw fetch) so that the
  // single-flight guard in api.js catches concurrent refreshes -- if the
  // dashboard fires listRepos() before this resolves, both share the same
  // /refresh Promise and the second one doesn't fail because the first
  // rotated the refresh cookie out from under it.
  const checkAuth = useCallback(async () => {
    try {
      await refreshTokens();
      setIsAuthenticated(true);
    } catch {
      setIsAuthenticated(false);
    } finally {
      setAuthChecked(true);
    }
  }, []);

  // After /login resolves the cookies are already set via Set-Cookie.
  // Re-running /refresh would re-rotate the just-issued refresh cookie
  // for no benefit AND race with any auth-fetch that fires from the
  // destination page. Just flip the flag and let the next page handle
  // its own data load.
  const onLoginSuccess = useCallback(() => {
    setIsAuthenticated(true);
    setAuthChecked(true);
  }, []);

  // Server-side logout: clears the refresh cookie AND revokes the
  // refresh-token hash on the User row. Then routes to /login via the
  // SPA router (no full reload -- cookies are already cleared, and a
  // hard reload would trigger another silent /refresh on the destination).
  const navigate = useNavigate();
  const logout = useCallback(async () => {
    await logoutApi();
    setIsAuthenticated(false);
    setAuthChecked(true);
    navigate("/login", { replace: true });
  }, [navigate]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, authChecked, checkAuth, onLoginSuccess, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}