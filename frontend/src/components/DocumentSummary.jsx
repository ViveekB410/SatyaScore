import { VERDICT_META } from '../lib/verdicts'

// Whole-text verdict by share: >= 1/3 of claims Hallucinated -> Hallucinated;
// else any Hallucinated or Uncertain -> Uncertain; else Verified (as the server).
function summarise(result) {
  if (result.document) return result.document
  // History entries saved before the API returned `document`: derive it.
  const c = result.claims
  const n = (v) => c.filter((x) => x.verdict === v).length
  const [nv, nu, nh] = [n('Verified'), n('Uncertain'), n('Hallucinated')]
  return {
    verdict: nh > 0 && nh * 3 >= c.length ? 'Hallucinated' : nh || nu ? 'Uncertain' : 'Verified',
    n_claims: c.length, n_verified: nv, n_uncertain: nu, n_hallucinated: nh,
    supported_fraction: c.length ? nv / c.length : 0,
  }
}

// Literal class strings so Tailwind keeps them.
const ACCENT = {
  Hallucinated: 'bg-flag-hallucinated',
  Uncertain: 'bg-flag-uncertain',
  Verified: 'bg-flag-verified',
}

function Tile({ dot, label, value }) {
  return (
    <div className="rounded-lg bg-subtle px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[13px] text-ink/60">
        <span className={`inline-block h-2 w-2 rounded-full ${dot}`} />
        {label}
      </div>
      <div className="mt-0.5 font-serif text-2xl font-semibold tabular-nums text-ink">{value}</div>
    </div>
  )
}

export default function DocumentSummary({ result }) {
  const d = summarise(result)
  const meta = VERDICT_META[d.verdict]
  const pct = (k) => (d.n_claims ? (k / d.n_claims) * 100 : 0)
  return (
    <div className="relative overflow-hidden rounded-xl border border-rule bg-card p-6 pl-7 shadow-card">
      <span className={`absolute inset-y-0 left-0 w-1 ${ACCENT[d.verdict]}`} />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[13px] font-medium uppercase tracking-wide text-ink/50">Whole text</p>
          <p className="mt-2 text-ink/70">
            <span className="font-serif text-4xl font-semibold tabular-nums text-ink">{d.n_verified}</span>
            <span className="ml-2">
              of {d.n_claims} claims supported ({Math.round(d.supported_fraction * 100)}%)
            </span>
          </p>
        </div>
        <span className={`rounded-full px-4 py-1.5 text-sm font-semibold ${meta.chip}`}>{meta.label}</span>
      </div>

      {/* composition bar: the same counts as the tiles, drawn to scale */}
      <div className="mt-5 flex h-2 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
        <span className="bg-flag-verified" style={{ width: `${pct(d.n_verified)}%` }} />
        <span className="bg-flag-uncertain" style={{ width: `${pct(d.n_uncertain)}%` }} />
        <span className="bg-flag-hallucinated" style={{ width: `${pct(d.n_hallucinated)}%` }} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <Tile dot="bg-flag-verified" label="Supported" value={d.n_verified} />
        <Tile dot="bg-flag-uncertain" label="Could not verify" value={d.n_uncertain} />
        <Tile dot="bg-flag-hallucinated" label="Not supported" value={d.n_hallucinated} />
      </div>
      <p className="mt-4 text-[13px] text-ink/50">
        Not supported when a third or more of the claims are not supported; fewer, or any claim that
        could not be verified, gives Could not verify.
      </p>
    </div>
  )
}
