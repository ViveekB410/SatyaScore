import * as React from 'react'
import { cn } from '@/lib/utils'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded border border-rule bg-card px-3 text-sm text-ink placeholder:text-muted/80 focus:border-navy focus:outline-none',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      'w-full resize-y rounded border border-rule bg-card p-4 text-base leading-relaxed text-ink placeholder:text-muted/80 focus:border-navy focus:outline-none read-only:bg-paper read-only:text-muted',
      className,
    )}
    {...props}
  />
))
Textarea.displayName = 'Textarea'
