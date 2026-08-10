"use client";

// Makes every Framer Motion animation in this portal respect the OS-level
// "reduce motion" accessibility setting automatically.
import { MotionConfig } from "framer-motion";

export default function MotionConfigProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
