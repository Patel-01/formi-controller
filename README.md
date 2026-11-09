# Formi Controller — Outcome-First Agent Loop

**Candidate:** Pankaj Patel &nbsp;·&nbsp; **Language:** Python 3.11 &nbsp;·&nbsp; **Storage:** SQLite WAL &nbsp;·&nbsp; **Date:** 2026-11-09

> An always-on controller that ingests call events, runs statistical experiments, detects incidents, and proposes config changes — continuously, every 15 simulated minutes, with no manual intervention.

---

## Quick start

```bash
pip install -r requirements.txt

# 1. Run the baseline (no-op controller)
python -m sim baseline --scenario scenarios/public_01_dev.yaml --run-dir runs/base01

# 2. Start the simulator
python -m sim serve --scenario scenarios/public_01_dev.yaml --run-dir runs/mine01   # :8700

# 3. Start the controller (in another terminal)
./run.sh http://127.0.0.1:8700

# 4. Grade
python -m sim grade --run runs/mine01 --baseline runs/base01 --out reports/public_01.md
```

Requires Python 3.11+. All dependencies in `requirements.txt`. No Docker required (but `run.sh` notes how to run in Docker if needed). The controller exits cleanly when the scenario finishes.

---

## Results

| Scenario | Conclusion Δ | Engagement Δ | Credits | Applied | Wall-clock |
|---|---|---|---|---|---|
| public_01_dev (3 wf, 7 days) | **+3.4%** | +3.5% | 49 | 10 | — |
| public_02_incidents (3 wf, 7 days) | **+2.2%** | +3.6% pickup | 70 | 11 | — |
| public_03_load (12 wf, 5 days) | **+6.2%** | +5.6% | 90 | 37 | 43 min |

Full grade tables are in [`reports/`](reports/). Detailed interpretation, design decisions, stakeholder responses, scale analysis and known weaknesses are in [`SUBMISSION.md`](SUBMISSION.md).

---

## What was built

| Capability | Status |
|---|---|
| C1 Event ingestion — idempotent, watermark, crash-restartable | ✅ Built |
| C5 Caller-ID health — 2-tick confirmation gate, auto-rotate | ✅ Built |
| C6 Variant experiments — z-test, Bonferroni, 300 calls/arm | ✅ Built |
| C8 Hallucination response — LLM suggest → validate → propose | ✅ Built |
| C9 Governance client — full lifecycle, timing, stale-base, auto-apply | ✅ Built |
| C12 Audit store — queryable SQLite `audit` table | ✅ Built |
| C13 Crash recovery — demonstrated kill/restart | ✅ Built |
| C7 Winner promotion (decay/rollback) | ⚠️ Partial — promotion yes, decay detection no |
| C2 Sub-cohort experiments | ⚠️ Cut — default cohort covers KPI headroom |
| C4 Per-person call-time optimisation | ⚠️ Cut — complexity vs. lift trade-off |
| C14 Observability / metrics endpoint | ⚠️ Cut — logs exist, no Prometheus exporter |

Rationale for every cut is in [SUBMISSION.md §2](SUBMISSION.md#2-scope-decisions).

---

## Crash recovery

```bash
./crash_recovery_test.sh http://127.0.0.1:8700
```

Script kills the controller mid-run on Day 3, restarts it, and verifies the scenario completes correctly. Evidence log: [`reports/crash_recovery.log`](reports/crash_recovery.log).

---

## Audit query

The audit store answers *"why did workflow X change, who approved it, what happened next?"*:

```sql
SELECT ts, action, detail
FROM audit
WHERE workflow_id = 'ks_cancel'
  AND ts >= '2027-01-04T00:00:00'
ORDER BY ts;
```

Output sample is in [SUBMISSION.md §10](SUBMISSION.md#10-audit--observability).

---

## Repository layout

```
controller/          Python source — ingestion, experiments, governance, detection, audit
scenarios/           public_01_dev · public_02_incidents · public_03_load
reports/             sim grade outputs for all 3 scenarios + crash recovery log
docs/                SIMULATOR.md (API contract)
stakeholders/        six memos; responses in SUBMISSION.md §3
tests/               unit tests for statistical utilities
run.sh               entry point — ./run.sh <SIM_URL>
crash_recovery_test.sh
SUBMISSION.md        full write-up: assumptions, scope, design, results, known weaknesses
requirements.txt
```

---

## Scale numbers (public_03_load)

| Metric | Value |
|---|---|
| Ingest throughput | ~3,300 events/sec |
| Decision lag per tick | ~4 s |
| DB size at D2 (12 workflows) | 795 MB |
| Wall-clock for 5 sim-days | 43 min |
| Where 10× breaks | SQLite single-writer → Postgres; schema ports directly |
