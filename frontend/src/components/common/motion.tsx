// Shared Framer Motion primitives and variants for consistent, tasteful motion.
// All motion respects prefers-reduced-motion via MotionConfig in main.tsx.
import {
  motion,
  type Variants,
  type Transition,
  type HTMLMotionProps,
} from "framer-motion";
import type { ReactNode } from "react";

export const easeOut: Transition["ease"] = [0.16, 1, 0.3, 1];

export const springSoft: Transition = {
  type: "spring",
  stiffness: 260,
  damping: 28,
  mass: 0.9,
};

/** Container that staggers its direct motion children on mount. */
export const staggerContainer: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.06, delayChildren: 0.04 },
  },
};

/** Standard "rise + fade" for cards, rows, and list items. */
export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: easeOut },
  },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.35, ease: easeOut } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.25, ease: easeOut } },
};

/** Route/page transition wrapper. */
export function PageTransition({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.32, ease: easeOut }}
    >
      {children}
    </motion.div>
  );
}

/**
 * Motion section that reveals its children with a stagger.
 * Wrap children in <MotionItem> to participate.
 */
export function MotionStagger({
  children,
  className,
  ...rest
}: HTMLMotionProps<"div"> & { children: ReactNode }) {
  return (
    <motion.div
      className={className}
      variants={staggerContainer}
      initial="hidden"
      animate="show"
      {...rest}
    >
      {children}
    </motion.div>
  );
}

export function MotionItem({
  children,
  className,
  variants = fadeInUp,
  ...rest
}: HTMLMotionProps<"div"> & { children: ReactNode }) {
  return (
    <motion.div className={className} variants={variants} {...rest}>
      {children}
    </motion.div>
  );
}

export { motion };
