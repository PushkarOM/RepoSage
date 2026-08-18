import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center cursor-pointer rounded-md font-mono font-medium select-none transition disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-strong",
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-paper hover:brightness-110 active:translate-y-px",
        ghost:
          "border border-rule text-ink hover:border-accent hover:text-accent bg-transparent",
      },
      size: {
        default: "h-9 px-4 text-sm",
        sm: "h-7 px-3 text-xs",
        lg: "h-11 px-6 text-base",
        link: "h-auto px-0 text-xs bg-transparent border-transparent hover:text-accent",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  }
);

function Button({ className, variant, size, type = "button", ...props }) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}

export { Button, buttonVariants };