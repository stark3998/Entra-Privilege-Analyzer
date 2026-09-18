// Animated number counter for KPIs. Respects reduced-motion (jumps to final value).
import { useEffect, useRef, useState } from "react";

interface AnimatedNumberProps {
  value: number;
  durationMs?: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
  /** Use locale grouping (e.g. 1,284). Ignored when decimals > 0 and value is float. */
  group?: boolean;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

export function AnimatedNumber({
  value,
  durationMs = 900,
  decimals = 0,
  suffix = "",
  prefix = "",
  className,
  group = true,
}: AnimatedNumberProps) {
  const [display, setDisplay] = useState(0);
  const frame = useRef<number>();
  const startTs = useRef<number>();
  const fromRef = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setDisplay(value);
      return;
    }
    const from = fromRef.current;
    const delta = value - from;
    startTs.current = undefined;

    const tick = (ts: number) => {
      if (startTs.current === undefined) startTs.current = ts;
      const elapsed = ts - startTs.current;
      const t = Math.min(1, elapsed / durationMs);
      // easeOutExpo
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
      setDisplay(from + delta * eased);
      if (t < 1) {
        frame.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = value;
      }
    };

    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [value, durationMs]);

  const formatted = display.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: group,
  });

  return (
    <span className={className}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}
