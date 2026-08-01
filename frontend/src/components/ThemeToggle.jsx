import { useTheme } from "@/lib/useTheme";
import { Button } from "@/components/ui/button";

function ThemeToggle() {
  const { mode, toggle } = useTheme();
  return (
    <Button variant="ghost" size="sm" onClick={toggle} aria-label={`Switch to ${mode === "dark" ? "light" : "dark"} mode`}>
      {mode === "dark" ? "☼ light" : "☾ dark"}
    </Button>
  );
}

export default ThemeToggle;