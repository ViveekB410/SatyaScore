# IVF vs exact search (PRD FR-03)

Demo corpus, 9351 passages; 417 gold claims with a source article in it. IVF: 97 clusters, nprobe 24 (the retriever's defaults).

| Index | R@3 | median latency / query | p95 latency |
| --- | --- | --- | --- |
| exact (flat, current) | 0.775 | 1.55 ms | 2.23 ms |
| IVF | 0.775 | 0.23 ms | 0.41 ms |

- ΔR@3 (IVF − exact): +0.000, 95% CI [+0.000, +0.000].
- Both are far inside the PRD's 100 ms retrieval target.
- **Decision: switch to IVF** — no measurable recall loss and faster.

