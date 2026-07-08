# Design notes

## Why table-to-table state (not in-memory passing)
Every agent persists its output to SQLite before the next runs. This is what makes
the pipeline restartable from any step and lets you re-run a single agent in
isolation. The cost is disk I/O; the benefit is reproducibility and crash-safety.

## Why hooks instead of fragile scrapers baked in
SwissADME, SwissTargetPrediction, IMPPAT and GeneCards have no stable public API,
and their HTML changes. Rather than ship brittle selectors that silently break, the
site interaction for each is one isolated method with the real request/Playwright
structure documented inline. Swap in your verified selectors (or a manual CSV export)
without touching the filtering/threshold logic, which is real and tested.

## Hub-gene metrics
MCC, MNC and DMNC are implemented from cytoHubba's published definitions on the
STRING graph via NetworkX, so hub ranking does not depend on Cytoscape being open.
When Cytoscape IS open, cytoHubba/MCODE can still be run through CyREST for
cross-checking.

## Restartability contract
`Store.step_status` records done/failed per step; `BaseAgent.execute` skips a step
whose status is done AND whose output table exists. `run --force` clears that.
