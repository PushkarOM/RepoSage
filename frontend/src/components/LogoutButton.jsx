import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function LogoutButton() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <button
      onClick={() => { logout(); navigate("/login"); }}
      className="fixed top-4 right-4 z-10 font-mono-ui text-xs text-(--color-steel) hover:text-(--color-amber) border border-white/10 rounded-md px-3 py-1.5 bg-(--color-slate) transition"
    >
      $ logout
    </button>
  );
}

export default LogoutButton;
