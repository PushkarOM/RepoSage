import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "./ui/button";

function LogoutButton() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => { logout(); navigate("/login"); }}
    >
      $ logout
    </Button>
  );
}

export default LogoutButton;