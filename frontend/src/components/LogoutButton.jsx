import { useAuth } from "../context/AuthContext";
import { Button } from "./ui/button";

function LogoutButton() {
  const { logout } = useAuth();

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={logout}
    >
      $ logout
    </Button>
  );
}

export default LogoutButton;