# Lane B status

## Requests to the owner
- Add `kuzu==0.11.3` to `pyproject.toml` (installed on the lane with `uv pip`; the graph falls back to plain Python without it).
- Add `band-sdk` to `pyproject.toml` when BAND goes live.
- Fixture: no company has a competitor-use + churn signal, so `/paths/competitor_displacement` is empty on it. Tests build one in code.

## Graph (`gtm/graph/`): done
- Engine: **kuzu 0.11.3** (21 MB wheel, embedded, works on the lane). Plain-Python traversal behind the same `paths()` is the fallback; tests hold both engines to identical output.
- One kuzu file per run in `data/gtm/graph/<run_id>.kuzu`, rebuilt when the run's graph changes; buffer pool capped at 64 MB.
- Ontology: Company, Person, Product, Competitor, Signal + **School** (added). Edges from SPEC + **attended**, **has_signal**, **uses** (Company→Competitor, derived when a signal names a competitor).
- Past employers not in the run become external Company nodes (`company:ext-<slug>`).
- Queries: `warm_intro` (shared past employer or school, to someone already contacted), `buying_cycle` (job post → matched company → persona from ICP), `competitor_displacement` (uses competitor + churn/complaint signal).
- Routes: `GET /api/gtm/runs/{id}/graph`, `GET /api/gtm/runs/{id}/paths/{kind}?target=p_3&engine=auto|kuzu|python`.
- Runs load from `gtm.pipeline.store` when it lands, else the fixture.
- Fixture result: 13 nodes, 14 edges; warm intro p_3 → Globex Pay → p_1 (plus p_2 → p_1); buying cycle sig_1 → Acme → Dana.

## BAND room (`gtm/band/`): next

## Tests
- `python -m pytest -q gtm/tests`: 25 passed.
