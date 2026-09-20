# Latency benchmark

- Device: **cuda**
- Single claims timed: 12 (first run discarded as warm-up)
- NLI top-k: 3, corpus: experiment (2674 passages)

## Per-stage timings across single claims (ms)
| Stage | mean | median |
| --- | --- | --- |
| claim_extraction | 6.3 | 6.5 |
| embedding | 17.4 | 15.2 |
| retrieval | 0.9 | 0.9 |
| nli | 80.2 | 36.3 |
| kg | 1066.1 | 11.3 |
| fusion | 0.1 | 0.1 |
| total | 1171.1 | 104.2 |

## PRD targets
| Metric | Measured | Target | Result |
| --- | --- | --- | --- |
| Per-claim total (mean) | 1171 ms | < 500 ms | **MISSED** |
| Per-claim total (median) | 104 ms | < 500 ms | **MET** |
| 10-claim document total | 2414 ms | < 3000 ms | **MET** |

_NLI is the dominant stage; on CPU the per-claim targets are expected to be MISSED. Re-run on a GPU (device=cuda) for the real numbers._

