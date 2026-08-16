# Run log

One entry per run. Never overwrite an entry — append.
This file is the source for the README results section.

Every row cites the run artefact it came from, by filename, in
`reports/runs/`. A row without a citation is an assertion, not a
measurement, and the chain from published number down to the raw
generated answer is what this project is for.

## Template

### Run YYYY-MM-DD-N

**Config:** generation=`...` judge=`...` embed=`...` rerank=`...`
top_k=`...` candidate_k=`...` threshold=`...`
**Commit:** `...`
**Changed since last run:** ...

| Config | hit@3 | Answer correct | Fabrication (OOS) | Artefact |
|--------|-------|----------------|-------------------|----------|
| dense | | | | `runs/...json` |
| hybrid | | | | `runs/...json` |
| hybrid_rerank | | | | `runs/...json` |

Per category (answer correct):

| Config | exact_term | semantic | multi_fact | out_of_scope | Artefact |
|--------|-----------|----------|------------|--------------|----------|
| dense | | | | | `runs/...json` |
| hybrid | | | | | `runs/...json` |
| hybrid_rerank | | | | | `runs/...json` |

**Observations:** what surprised me, what I expected and did not get.
