import type { Claim, DocumentSummary, Verdict } from './types'

// Display wording and styling per verdict: the verdicts are shown by their
// names, Verified / Uncertain / Hallucinated. Class strings are literal so
// Tailwind's scanner keeps them. Amber TEXT uses flag-unc (AA); the lighter
// flag-unc-accent is for underlines and bars only.
export const VERDICT: Record<Verdict, { label: string; chip: string; mark: string; bar: string; text: string }> = {
  Hallucinated: {
    label: 'Hallucinated',
    chip: 'border-flag-no/30 bg-flag-no-bg text-flag-no',
    mark: 'bg-flag-no-bg decoration-flag-no',
    bar: 'bg-flag-no',
    text: 'text-flag-no',
  },
  Uncertain: {
    label: 'Uncertain',
    chip: 'border-flag-unc/30 bg-flag-unc-bg text-flag-unc',
    mark: 'bg-flag-unc-bg decoration-flag-unc-accent',
    bar: 'bg-flag-unc-accent',
    text: 'text-flag-unc',
  },
  Verified: {
    label: 'Verified',
    chip: 'border-flag-yes/30 bg-flag-yes-bg text-flag-yes',
    mark: 'bg-flag-yes-bg decoration-flag-yes',
    bar: 'bg-flag-yes',
    text: 'text-flag-yes',
  },
}

export const isFlagged = (c: Claim) => c.verdict !== 'Verified'

// Same rule as the server (member1_model/cmhsa.py aggregate_document).
export const DOC_HALLUCINATED_SHARE = 1 / 3

/** The server's whole-text verdict, or the same share rule applied locally:
 * >= 1/3 of claims Hallucinated -> Hallucinated; else any Hallucinated or
 * Uncertain claim -> Uncertain; else Verified. */
export function summarise(claims: Claim[], doc?: DocumentSummary | null): DocumentSummary {
  if (doc) return doc
  const count = (v: Verdict) => claims.filter((c) => c.verdict === v).length
  const [nv, nu, nh] = [count('Verified'), count('Uncertain'), count('Hallucinated')]
  return {
    verdict: nh > 0 && nh * 3 >= claims.length ? 'Hallucinated' : nh || nu ? 'Uncertain' : 'Verified',
    n_claims: claims.length,
    n_verified: nv,
    n_uncertain: nu,
    n_hallucinated: nh,
    supported_fraction: claims.length ? nv / claims.length : 0,
  }
}

/** Overall support score of the passage: the average of its claims' support scores
 * (0 = contradicted, 1 = supported). Same number as the API's overall_score (PRD). */
export function overallScore(claims: Claim[]): number | null {
  return claims.length ? claims.reduce((s, c) => s + c.hallu_score, 0) / claims.length : null
}

export function summaryLine(d: DocumentSummary): string {
  const claims = `${d.n_claims} ${d.n_claims === 1 ? 'claim' : 'claims'}`
  return `${claims} · ${d.n_verified} verified · ${d.n_uncertain} uncertain · ${d.n_hallucinated} hallucinated`
}
