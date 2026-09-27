import { motion, useReducedMotion } from 'framer-motion'
import type { ReactNode } from 'react'

/** Fade and rise 8px, staggered by `order`. Reduced motion: instant, no movement. */
export default function Reveal({ order = 0, children, className }: { order?: number; children: ReactNode; className?: string }) {
  const reduce = useReducedMotion()
  return (
    <motion.div
      className={className}
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduce ? { duration: 0 } : { duration: 0.22, ease: 'easeOut', delay: order * 0.09 }}
    >
      {children}
    </motion.div>
  )
}
