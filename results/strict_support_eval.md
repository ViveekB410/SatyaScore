# Strict support: only on-topic passages may verify a claim

**Decision rule (fixed before running):** adopt "strict" only if on TRAIN (a) hallucinations marked Verified are fewer, (b) false alarms not more, (c) true claims marked Verified fall by at most 10%; and on FRESH true Wikipedia sentences (seed 13) (d) claims marked Verified fall by at most 10% and false alarms are not more.

## train (303 claims) — decides

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 157/303 | 152/258 | **28/45** | 9/258 | 5/45 | 109 |
| strict | 52/303 | 47/258 | **7/45** | 11/258 | 5/45 | 233 |

## test (76 claims) — reported only

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 38/76 | 38/66 | **8/10** | 3/66 | 0/10 | 27 |
| strict | 15/76 | 15/66 | **3/10** | 7/66 | 0/10 | 51 |

## round3 (40 claims) — reported only

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 18/40 | 16/25 | **1/15** | 2/25 | 2/15 | 19 |
| strict | 15/40 | 13/25 | **1/15** | 2/25 | 2/15 | 22 |

## fresh (126 claims) — decides

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 115/126 | 115/126 | **—** | 3/126 | — | 8 |
| strict | 86/126 | 86/126 | **—** | 6/126 | — | 34 |

## Decision

(a) hallucinations Verified 28 -> 7: met; (b) false alarms 9 -> 11: NOT met; (c) true claims Verified 152 -> 47: NOT met; (d) fresh Verified 115 -> 86, false alarms 3 -> 6: NOT met.

**Do not adopt; the live rule stays "gated".**
