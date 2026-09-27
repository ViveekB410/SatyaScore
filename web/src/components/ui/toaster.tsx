import { Toaster as Sonner } from 'sonner'

// shadcn/ui toast (sonner), re-themed to the paper/navy palette.
export function Toaster() {
  return (
    <Sonner
      position="bottom-right"
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            'flex w-full items-start gap-3 rounded border border-rule border-l-4 border-l-navy bg-card px-4 py-3 font-sans text-sm text-ink shadow-overlay',
          title: 'font-medium',
          description: 'text-[13px] text-muted',
          error: 'border-l-flag-no',
        },
      }}
    />
  )
}
