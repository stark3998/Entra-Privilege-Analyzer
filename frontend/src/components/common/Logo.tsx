// Professional brand mark for the Entra Privilege Analyzer.
// A geometric filled shield with a keyhole (security + least-privilege access),
// rendered as a single evenodd path so the keyhole is cleanly knocked out.

interface LogoProps {
  className?: string;
}

/** The bare glyph — inherits `currentColor`. Use inside a colored badge. */
export function LogoMark({ className }: LogoProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M11.6 2.3a1 1 0 0 1 .8 0l7.4 3.3a1 1 0 0 1 .59.91v9a1 1 0 0 1-.59.91l-7.4 3.3a1 1 0 0 1-.8 0l-7.4-3.3a1 1 0 0 1-.59-.91v-9a1 1 0 0 1 .59-.91l7.4-3.3Zm.4 5.45a2.45 2.45 0 0 0-1.13 4.62l-.66 3.06a.62.62 0 0 0 .6.75h2.38a.62.62 0 0 0 .6-.75l-.66-3.06A2.45 2.45 0 0 0 12 7.75Z"
        fill="currentColor"
      />
    </svg>
  );
}

const SIZE: Record<NonNullable<LogoBadgeProps["size"]>, { box: string; icon: string; radius: string }> = {
  sm: { box: "h-8 w-8", icon: "h-[18px] w-[18px]", radius: "rounded-lg" },
  md: { box: "h-9 w-9", icon: "h-5 w-5", radius: "rounded-xl" },
  lg: { box: "h-16 w-16", icon: "h-8 w-8", radius: "rounded-2xl" },
};

interface LogoBadgeProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

/** The full brand badge: gradient rounded square with the white mark. */
export function LogoBadge({ size = "md", className = "" }: LogoBadgeProps) {
  const s = SIZE[size];
  return (
    <div
      className={`relative flex ${s.box} items-center justify-center ${s.radius} bg-brand-gradient shadow-glow ${className}`}
    >
      {/* subtle top highlight for depth */}
      <span className={`pointer-events-none absolute inset-0 ${s.radius} bg-gradient-to-b from-white/25 to-transparent`} />
      <LogoMark className={`relative ${s.icon} text-white`} />
    </div>
  );
}
