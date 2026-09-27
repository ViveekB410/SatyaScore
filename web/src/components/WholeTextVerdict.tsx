import { VERDICT, summaryLine } from '@/lib/verdicts'
import type { DocumentSummary } from '@/lib/types'
import { cn } from '@/lib/utils'

// Whole-text verdict (the guide's "score for the whole text"), by share of
// hallucinated claims; a text with any hallucinated claim is never Verified.
export default function WholeTextVerdict({ doc }: { doc: DocumentSummary }) {
  const v = VERDICT[doc.verdict]
  return (
    <section aria-labelledby="whole-text" className="relative rounded border border-rule bg-card py-5 pl-7 pr-5">
      <span className={cn('absolute inset-y-0 left-0 w-1 rounded-l', v.bar)} aria-hidden="true" />
      <h2 id="whole-text" className="label-caps">
        Whole text
      </h2>
      <p className={cn('mt-1.5 font-serif text-[26px] font-semibold leading-tight', v.text)}>{v.label}</p>
      <p className="mt-2 text-[15px] text-ink">{summaryLine(doc)}</p>
      <p className="mt-2 text-[13px] text-muted">
        Hallucinated when a third or more of the claims are hallucinated. Fewer hallucinated claims, or any
        uncertain claim, make it Uncertain; Verified needs every claim verified.
      </p>
    </section>
  )
}
