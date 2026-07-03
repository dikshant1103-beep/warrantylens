"use client";

import { useEffect, useRef, useState } from "react";

/** Counts up from 0 to `value` with an ease-out curve. Renders "—" for null. */
export function AnimatedNumber({
  value,
  decimals = 0,
  duration = 900,
  suffix = "",
}: {
  value: number | null | undefined;
  decimals?: number;
  duration?: number;
  suffix?: string;
}) {
  const [display, setDisplay] = useState(0);
  const raf = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (value === null || value === undefined) return;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setDisplay(value * eased);
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [value, duration]);

  if (value === null || value === undefined) return <>—</>;
  return (
    <>
      {display.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </>
  );
}
