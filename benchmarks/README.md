# Public benchmarks (data not committed)

`public_benchmark_eval.py` reads these files from `benchmarks/data/` (git-ignored; third-party data):

| File | Source | Licence |
|---|---|---|
| `fever_paper_dev.jsonl` | https://fever.ai/download/fever/paper_dev.jsonl | CC BY-SA 3.0 |
| `mushroom_{hi,en}_{validation,test}.parquet` | https://huggingface.co/datasets/Helsinki-NLP/mu-shroom (`{lang}/{split}-00000-of-00001.parquet`) | CC BY 4.0 |

Download (PowerShell, from the project folder):

```powershell
New-Item -ItemType Directory -Force benchmarks\data | Out-Null
.venv\Scripts\python.exe -c "import requests; u={'fever_paper_dev.jsonl':'https://fever.ai/download/fever/paper_dev.jsonl'}; u.update({f'mushroom_{l}_{s}.parquet': f'https://huggingface.co/datasets/Helsinki-NLP/mu-shroom/resolve/main/{l}/{s}-00000-of-00001.parquet' for l in ('hi','en') for s in ('validation','test')}); [open('benchmarks/data/'+n,'wb').write(requests.get(x,timeout=120).content) for n,x in u.items()]"
```

Then: `public_benchmark_eval.py` (live system, resumable cache `results/_public_benchmarks_cache.jsonl`),
`summarise_public_benchmarks.py` (JSON summary) and `public_benchmark_sources.py` (deciding sources).
Protocol, fixed before the run: `results/public_benchmarks_PROTOCOL.md`.
