"use client";

// Makes every Framer Motion animation in the app respect the OS-level
// "reduce motion" accessibility setting automatically — the CSS
// `prefers-reduced-motion` rule in globals.css only catches native CSS
// transitions/animations, not Framer Motion's JS-driven ones. This is the
// single place that needs to know about it; individual screens don't.
import { MotionConfig } from "framer-motion";

export default function MotionConfigProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
