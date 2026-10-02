import { HIGH, LOW, ScoreBar } from '@/components/ScoresPanel'
import { VERDICT, summaryLine } from '@/lib/verdicts'
import type { DocumentSummary } from '@/lib/types'
import { cn } from '@/lib/utils'

// Whole-text verdict (the guide's "score for the whole text"), by share of
// hallucinated claims; a text with any hallucinated claim is never Verified.
// Beside it, the overall support score (average of the claims' scores); side by
// side on wide screens, stacked on phones.
// The two lists in "How is this decided?" share a fixed first column so they line up.
const ROWS = 'grid gap-x-6 gap-y-2.5 sm:grid-cols-[7.5rem_1fr]'

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
      <details className="group mt-3">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded text-[13px] text-navy underline decoration-rule underline-offset-4 hover:decoration-navy focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy [&::-webkit-details-marker]:hidden">
          How is this decided?
          <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3 transition-transform group-open:rotate-180">
            <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </summary>
        <div className="mt-3 rounded border border-rule px-4 text-[13px]">
          <dl className={cn(ROWS, 'py-3')}>
            <dt className="font-medium text-flag-no">Hallucinated</dt>
            <dd className="text-muted">a third or more of the claims are hallucinated</dd>
            <dt className="font-medium text-flag-unc">Uncertain</dt>
            <dd className="text-muted">some claims are hallucinated or uncertain, but fewer than a third hallucinated</dd>
            <dt className="font-medium text-flag-yes">Verified</dt>
            <dd className="text-muted">every claim is verified</dd>
          </dl>
          <dl className={cn(ROWS, 'border-t border-rule py-3')}>
            <dt className="font-medium text-ink">Overall score</dt>
            <dd className="text-muted">
              the average of the claims’ support scores: 0 = contradicted by evidence, 1 = supported (bar ticks at{' '}
              {LOW} and {HIGH}). The verdict above is the result; the average can hide one false claim among true ones.
            </dd>
          </dl>
        </div>
      </details>
    </section>
  )
}
