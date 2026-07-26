import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Ingest from "./pages/Ingest";
import ThreadList from "./pages/ThreadList";
import Chat from "./pages/Chat";
import LogoutButton from "./components/LogoutButton";

function RequireAuth({ children }) {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" replace />;
}

function App() {
  const { token } = useAuth();

  return (
    <div className="relative">
      {token && <LogoutButton />}
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/dashboard" replace /> : <Auth />} />
        <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/ingest" element={<RequireAuth><Ingest /></RequireAuth>} />
        <Route path="/repos/:owner/:name/threads" element={<RequireAuth><ThreadList /></RequireAuth>} />
        <Route path="/repos/:owner/:name/threads/:threadId" element={<RequireAuth><Chat /></RequireAuth>} />
        <Route path="*" element={<Navigate to={token ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </div>
  );
}

export default App;
