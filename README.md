# Network Pharmacology Platform

A modular, restartable multi-agent pipeline that takes a **medicinal plant** and a
**disease** and runs the full network-pharmacology workflow — phytochemical
extraction → standardization → ADME → target prediction → disease genes →
intersection → PPI → enrichment → Cytoscape networks → hub genes → report — with
no manual steps after "Run Pipeline."

Each agent is independent, reads the previous agent's output table, writes exactly
one output table (mirrored to a CSV with the spec's filename), and records its
status so the pipeline can **resume from the last completed step**.

## Architecture

```
config/config.yaml   ← single source of truth for every threshold & path
        │
orchestrator.py (LangGraph StateGraph)  ── runs agents in order, checkpointed
        │
agents/            each subclasses BaseAgent (skip-if-done, logging, error capture)
   extractor → standardize → adme → targets → disease → intersection
   → ppi → enrichment → hubgenes → cytoscape → report
        │
db.py (SQLite)  ← intermediate tables + step_status ; every table also → outputs/*.csv
```

State flows table-to-table through the SQLite `Store`; nothing is passed in
memory, so any step can be re-run in isolation (`step <name>`) or resumed.

## What runs live vs. what needs your environment

| Agent | Status in this repo |
|------|---------------------|
| 2 Standardize (RDKit) | **Fully working** |
| 6 Intersection | **Fully working** |
| 7 PPI (STRING REST) | **Fully working** — public STRING API |
| 8 Enrichment (Enrichr REST) | **Fully working** — public Enrichr API |
| 10 Hub genes (Degree/Betweenness/Closeness/MCC/MNC/DMNC) | **Fully working** |
| 9 Cytoscape — GraphML export | **Fully working** (no Cytoscape needed) |
| 9 Cytoscape — styling/PNG/SVG/PDF/.cys | needs local **Cytoscape + CyREST** on :1234 |
| 1 Extractor — PubChem enrichment | Real PUG REST; needs internet |
| 1 Extractor — IMPPAT plant→compound list | **Hook** (no API): scrape or curated CSV |
| 3 ADME (SwissADME) | **Playwright hook** (no API); filtering logic is real |
| 4 Targets (SwissTargetPrediction) | **Playwright hook** (no API); threshold logic is real |
| 5 Disease (DisGeNET/GeneCards/OMIM) | DisGeNET real (key-gated); others hooks |
| 11 Report | **Fully working**; narrative uses Claude API if `ANTHROPIC_API_KEY` set, else templated |

The three hook agents run offline with clearly-labelled demo data so the whole
pipeline executes end-to-end out of the box; each hook is a single isolated
method you replace with real scraping/imports without touching anything else.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # for ADME + target-prediction agents
```

Secrets come from the environment, never from YAML:

```bash
export ANTHROPIC_API_KEY=...          # Agent 11 narrative (optional)
export DISGENET_API_KEY=...           # Agent 5 DisGeNET (optional)
export OMIM_API_KEY=...               # Agent 5 OMIM (optional)
```

For Agent 9's live features, start Cytoscape (≥3.9) with the apps installed
(stringApp, cytoHubba, MCODE, ClueGO) and leave it running; CyREST listens on
`http://127.0.0.1:1234`.

## Run

```bash
# edit config/config.yaml -> run.plant and run.disease, then:
python -m netpharm.cli run              # full pipeline, resumes automatically
python -m netpharm.cli run --force      # ignore cache, recompute all
python -m netpharm.cli step ppi         # re-run one agent
python -m netpharm.cli status           # step status table

streamlit run src/netpharm/ui/streamlit_app.py   # UI: inputs, tables, downloads
```

Outputs land in `outputs/`: one CSV per agent (spec filenames), `networks/*.graphml`
(+ PNG/SVG/PDF/.cys when Cytoscape is live), and `report/report.{md,docx,pdf,html}`.

## Build a desktop app (.exe / Mac / Linux)

To ship this as a double-click application that opens in the browser (no Python
needed by the end user), see **packaging/README_PACKAGING.md**. In short, run the
build script for your OS from the project root:

```bash
packaging\build_windows.bat      # Windows  -> dist/NetworkPharmacology/NetworkPharmacology.exe
bash packaging/build_macos.sh     # macOS
bash packaging/build_linux.sh     # Linux
```

Executables are OS-specific and must be built on the OS they target; Cytoscape and
Playwright remain external. Details and caveats are in the packaging guide.

## Tests

```bash
pytest tests/ -v
```

The tests cover the deterministic agents (intersection frequencies, the MCC
definition against a known triangle, hub ranking, network node-typing) and run
with no external services.

## Extending it

Add a source or tool without editing existing agents:

1. Subclass `BaseAgent`, set `name`, `output_table`, `requires`, implement `run`.
2. Insert it into `AGENT_SEQUENCE` in `agents/__init__.py`.

Because every agent's contract is "read named tables → write one named table,"
new agents compose automatically and inherit skip-if-done, logging, and status.
