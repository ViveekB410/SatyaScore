import { VERDICT_META } from '../lib/verdicts'

// Whole-text verdict. Judged by the WORST claim (any unsupported claim makes the
// text unsupported), never by an average that could hide one false claim.
function summarise(result) {
  if (result.document) return result.document
  // History entries saved before the API returned `document`: derive it.
  const c = result.claims
  const n = (v) => c.filter((x) => x.verdict === v).length
  const [nv, nu, nh] = [n('Verified'), n('Uncertain'), n('Hallucinated')]
  return {
    verdict: nh ? 'Hallucinated' : nu ? 'Uncertain' : 'Verified',
    n_claims: c.length, n_verified: nv, n_uncertain: nu, n_hallucinated: nh,
    supported_fraction: c.length ? nv / c.length : 0,
  }
}

export default function DocumentSummary({ result }) {
  const d = summarise(result)
  const meta = VERDICT_META[d.verdict]
  return (
    <div className="rounded-md border border-rule bg-white p-5">
      <p className="text-xs uppercase tracking-wide text-ink/50">Whole text</p>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <span className={`rounded px-2.5 py-1 text-sm font-medium ${meta.chip}`}>{meta.label}</span>
        <span className="text-sm text-ink/70">
          {d.n_verified} of {d.n_claims} claims supported
          {' '}({Math.round(d.supported_fraction * 100)}%)
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-ink/60">
        <span>Supported: {d.n_verified}</span>
        <span>Could not verify: {d.n_uncertain}</span>
        <span>Not supported: {d.n_hallucinated}</span>
      </div>
      <p className="mt-3 text-xs text-ink/50">
        The text is judged by its weakest claim: one unsupported claim marks the whole text.
      </p>
    </div>
  )
}
