import { createContext, useContext, useState } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("reposage_token"));

  function login(newToken) {
    localStorage.setItem("reposage_token", newToken);
    setToken(newToken);
  }

  function logout() {
    localStorage.removeItem("reposage_token");
    setToken(null);
  }

  return <AuthContext.Provider value={{ token, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
