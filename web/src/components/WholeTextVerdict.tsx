import { HIGH, LOW, ScoreBar } from '@/components/ScoresPanel'
import { VERDICT, summaryLine } from '@/lib/verdicts'
import type { DocumentSummary } from '@/lib/types'
import { cn } from '@/lib/utils'

// Whole-text verdict (the guide's "score for the whole text"), by share of
// hallucinated claims; a text with any hallucinated claim is never Verified.
// Beside it, the overall support score (average of the claims' scores); side by
// side on wide screens, stacked on phones.
export default function WholeTextVerdict({ doc, score }: { doc: DocumentSummary; score: number | null }) {
  const v = VERDICT[doc.verdict]
  return (
    <section aria-labelledby="whole-text" className="relative rounded border border-rule bg-card py-5 pl-7 pr-5">
      <span className={cn('absolute inset-y-0 left-0 w-1 rounded-l', v.bar)} aria-hidden="true" />
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
        <div>
          <h2 id="whole-text" className="label-caps">
            Whole text
          </h2>
          <p className={cn('mt-1.5 font-serif text-[26px] font-semibold leading-tight', v.text)}>{v.label}</p>
        </div>
        {score != null && (
          <div className="border-t border-rule pt-3 sm:border-l sm:border-t-0 sm:pl-8 sm:pt-0 sm:text-right">
            <h3 className="label-caps">Overall score</h3>
            <p className="mt-1.5 font-serif text-[26px] font-semibold leading-tight tabular-nums text-ink">
              {score.toFixed(2)}
              <span className="ml-1 font-sans text-[14px] font-normal text-muted">/ 1</span>
            </p>
            <ScoreBar score={score} bar="bg-navy" className="mt-2 w-40" />
          </div>
        )}
      </div>
      <p className="mt-3 text-[15px] text-ink">{summaryLine(doc)}</p>
      <p className="mt-2 text-[13px] text-muted">
        Hallucinated when a third or more of the claims are hallucinated. Fewer hallucinated claims, or any
        uncertain claim, make it Uncertain; Verified needs every claim verified. The overall score is the average
        support score of the claims (0 = contradicted by evidence, 1 = supported; ticks at {LOW} and {HIGH}); the
        verdict, not the average, is the result.
      </p>
    </section>
  )
}
