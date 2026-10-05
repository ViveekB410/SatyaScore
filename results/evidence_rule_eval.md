# Evidence rule: Verified only with a supporting passage (capped / capped_strong)

**Decision rule (fixed before running):** a candidate is adopted only if on TRAIN (a) hallucinations marked Verified are fewer, (b) false alarms not more, (c) true claims marked Verified fall by at most 10%; and on FRESH true Wikipedia sentences (seed 17, unseen) (d) claims marked Verified fall by at most 10% and false alarms are not more. Both qualify: fewer train hallucinations Verified wins; tie: capped.

## train (303 claims) — decides

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 157/303 | 152/258 | **27/45** | 9/258 | 5/45 | 110 |
| capped | 140/303 | 135/258 | **27/45** | 9/258 | 5/45 | 127 |
| capped_strong | 112/303 | 107/258 | **12/45** | 10/258 | 5/45 | 169 |

## test (76 claims) — reported only

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 38/76 | 38/66 | **8/10** | 3/66 | 0/10 | 27 |
| capped | 35/76 | 35/66 | **8/10** | 3/66 | 0/10 | 30 |
| capped_strong | 22/76 | 22/66 | **5/10** | 4/66 | 0/10 | 45 |

## round3 (40 claims) — reported only

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 18/40 | 16/25 | **1/15** | 2/25 | 2/15 | 19 |
| capped | 18/40 | 16/25 | **1/15** | 2/25 | 2/15 | 19 |
| capped_strong | 15/40 | 13/25 | **1/15** | 2/25 | 2/15 | 22 |

## fresh (128 claims) — decides

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 113/128 | 113/128 | **—** | 4/128 | — | 11 |
| capped | 104/128 | 104/128 | **—** | 4/128 | — | 20 |
| capped_strong | 97/128 | 97/128 | **—** | 4/128 | — | 27 |

## common sense (15 claims) — reported only

| rule | correct | true claims Verified | **hallucinations Verified** | false alarms | caught | Uncertain |
|---|---|---|---|---|---|---|
| gated | 5/15 | 5/6 | **9/9** | 1/6 | 0/9 | 0 |
| capped | 5/15 | 5/6 | **7/9** | 1/6 | 0/9 | 2 |
| capped_strong | 6/15 | 5/6 | **4/9** | 1/6 | 1/9 | 4 |

## Decision

- **capped**: (a) hallucinations Verified 27 -> 27: NOT met; (b) false alarms 9 -> 9: met; (c) true claims Verified 152 -> 135: NOT met; (d) fresh Verified 113 -> 104, false alarms 4 -> 4: met.
- **capped_strong**: (a) hallucinations Verified 27 -> 12: met; (b) false alarms 9 -> 10: NOT met; (c) true claims Verified 152 -> 107: NOT met; (d) fresh Verified 113 -> 97, false alarms 4 -> 4: NOT met.

**Do not adopt; the live rule stays "gated".**
