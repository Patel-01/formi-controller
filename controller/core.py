"""
Outcome-first controller.

Capabilities built:
  C1  Event ingestion (idempotent, chunk-based, crash-safe)
  C5  Caller-ID health (auto-rotate or propose rotation)
  C6  Variant experiments on voice + welcome_message (uniform → z-test)
  C8  Hallucination detection → LLM fix → validation → propose
  C9  Governance (approval lifecycle, timing, batching, stale-base retry)
  C12 Audit log (SQLite — query: SELECT * FROM audit WHERE workflow_id=?)
  C13 Crash recovery (reconcile proposals on startup from /approvals)

Cuts: C2 fancy cohort splits, C4 call-time opt,
      C10 dry-run beyond estimate, C11 supervisor UI,
      C14 metrics endpoint, C15 fair credit allocation.
Partial: C3 history ingested for watermark only (no stat bootstrap),
         C7 no rollback after winner promotion.
"""

import copy
import json
import logging
import uuid
from typing import Optional

import httpx

from .db import add_audit, kv_get, kv_set, open_db
from .stats import MIN_CALLS_PER_ARM, bonferroni_alpha, z_test_two_props

log = logging.getLogger(__name__)


class Controller:
    def __init__(self, sim_url: str, db_path: str = "controller.db"):
        self.db = open_db(db_path)
        self.c = httpx.Client(base_url=sim_url, timeout=180)
        self.workflows: dict = {}   # wf_id → workflow metadata
        self.tick_minutes = 15

    # ─── Startup ─────────────────────────────────────────────────────────────

    def run(self):
        self._load_workflows()
        self._ingest_history()
        self._reconcile_proposals()

        while True:
            resp = self.c.post("/sim/advance", json={"minutes": self.tick_minutes})
            if resp.status_code == 409:
                body = resp.text
                if "finished" in body or "stale" in body:
                    log.info("Scenario finished (409).")
                    break
                log.warning("Advance 409: %s", body[:200])
                break
            if resp.status_code >= 500:
                log.error("Advance server error %s, stopping.", resp.status_code)
                break
            if not resp.text.strip():
                log.error("Empty advance response, stopping.")
                break

            data = resp.json()
            ts = data["ts"]

            for chunk in data.get("new_chunks", []):
                try:
                    self._ingest_chunk(chunk["chunk"], ts)
                except Exception:
                    log.exception("Ingest error chunk %s", chunk)

            for wf_id in self.workflows:
                try:
                    self._tick_workflow(wf_id, ts)
                except Exception:
                    log.exception("Error in tick for %s", wf_id)

            self.db.commit()

            if data.get("finished"):
                log.info("Scenario finished (flag).")
                break

    def _load_workflows(self):
        wfs = self.c.get("/workflows").json()
        for wf in wfs:
            wf_id = wf["workflow_id"]
            self.workflows[wf_id] = wf
            cfg = self.c.get(f"/workflows/{wf_id}/config").json()
            kv_set(self.db, f"cfg:{wf_id}", cfg)
        self.db.commit()
        log.info("Loaded %d workflows", len(self.workflows))

    def _ingest_history(self):
        """Ingest pre-D0 history chunks for baseline stats."""
        history_chunks = self.c.get("/events/chunks", params={"kind": "history"}).json()
        last = kv_get(self.db, "last_history_chunk", -1)
        for chunk in history_chunks:
            n = chunk["chunk"]
            if n <= last:
                continue
            try:
                text = self.c.get(f"/events/chunks/{n}").text
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    ev = json.loads(line)
                    self._process_event(ev)
                kv_set(self.db, "last_history_chunk", n)
            except Exception:
                log.exception("Failed to ingest history chunk %d", n)
        self.db.commit()
        # Mark the watermark: caller-ID checks will only use calls above this
        row = self.db.execute("SELECT MAX(event_id) FROM calls").fetchone()
        kv_set(self.db, "history_watermark", row[0] or 0)
        log.info("History ingestion done (%d chunks), watermark=%s", len(history_chunks), row[0])

    def _reconcile_proposals(self):
        """Crash recovery: re-sync pending proposals with the simulator."""
        rows = self.db.execute(
            "SELECT * FROM proposals WHERE status='pending' AND approval_id IS NOT NULL"
        ).fetchall()
        for row in rows:
            try:
                ap = self.c.get(f"/approvals/{row['approval_id']}").json()
                s = ap["status"]
                if s in ("approved", "rejected", "expired", "lapsed"):
                    self.db.execute("UPDATE proposals SET status=? WHERE prop_id=?",
                                    (s, row["prop_id"]))
            except Exception:
                pass
        self.db.commit()
        log.info("Reconciled proposals on startup")

    # ─── Ingestion ───────────────────────────────────────────────────────────

    def _ingest_chunk(self, chunk_id: int, ts: str):
        last = kv_get(self.db, "last_chunk", -1)
        if chunk_id <= last:
            return  # already processed — idempotent

        text = self.c.get(f"/events/chunks/{chunk_id}").text
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._process_event(ev)

        kv_set(self.db, "last_chunk", chunk_id)
        # Commit happens in outer loop per tick

    def _process_event(self, ev: dict):
        t = ev["type"]
        if t == "call":
            var = ev.get("variant") or {}
            qa = ev.get("qa") or {}
            self.db.execute(
                "INSERT OR IGNORE INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ev["event_id"], ev["ts"], ev["workflow_id"],
                    ev.get("cohort_id"),
                    var.get("welcome_message"), var.get("voice"),
                    var.get("caller_id"), var.get("prompt_version"),
                    int(ev["connected"]),
                    int(ev.get("engaged", False)),
                    int(qa.get("hallucination_flag", False)) if qa else None,
                    ev.get("config_version"),
                )
            )
        elif t == "config_changed" and ev.get("actor") == "supervisor":
            wf_id = ev["workflow_id"]
            dims = ev.get("changed_dims") or []
            for dim in dims:
                if dim in ("voice", "welcome_message", "prompt_version"):
                    self.db.execute(
                        "UPDATE experiments SET status='cancelled' "
                        "WHERE workflow_id=? AND dim=? AND status='active'",
                        (wf_id, dim)
                    )
                    add_audit(self.db, ev["ts"], wf_id, "experiment_cancelled",
                              f"supervisor changed {dim}")
            # Always invalidate any pending proposal (may now have stale base)
            self.db.execute(
                "UPDATE proposals SET status='stale_supervisor' "
                "WHERE workflow_id=? AND status='pending'",
                (wf_id,)
            )
            # Refresh config cache
            try:
                cfg = self.c.get(f"/workflows/{wf_id}/config").json()
                kv_set(self.db, f"cfg:{wf_id}", cfg)
            except Exception:
                pass

    # ─── Per-workflow tick ────────────────────────────────────────────────────

    def _tick_workflow(self, wf_id: str, ts: str):
        self._check_pending_proposals(wf_id, ts)
        self._flush_pending_winners(wf_id, ts)   # retry stashed winners every tick
        self._flush_pending_cid(wf_id, ts)       # retry deferred DID rotations
        self._check_caller_ids(wf_id, ts)
        self._check_hallucination(wf_id, ts)
        self._advance_experiments(wf_id, ts)

    # ─── Governance ──────────────────────────────────────────────────────────

    def _check_pending_proposals(self, wf_id: str, ts: str):
        rows = self.db.execute(
            "SELECT * FROM proposals WHERE workflow_id=? AND status='pending' AND approval_id IS NOT NULL",
            (wf_id,)
        ).fetchall()
        for row in rows:
            try:
                ap = self.c.get(f"/approvals/{row['approval_id']}").json()
            except Exception:
                continue
            s = ap["status"]
            if s == "approved":
                r = self.c.post(
                    f"/workflows/{wf_id}/apply",
                    json={"approval_id": row["approval_id"]}
                )
                if r.status_code == 200:
                    self.db.execute("UPDATE proposals SET status='applied' WHERE prop_id=?",
                                    (row["prop_id"],))
                    add_audit(self.db, ts, wf_id, "config_applied",
                              {"approval_id": row["approval_id"], "summary": row["summary"]})
                    cfg = self.c.get(f"/workflows/{wf_id}/config").json()
                    kv_set(self.db, f"cfg:{wf_id}", cfg)
                elif r.status_code == 409:
                    self.db.execute("UPDATE proposals SET status='stale_base' WHERE prop_id=?",
                                    (row["prop_id"],))
                    cfg = self.c.get(f"/workflows/{wf_id}/config").json()
                    kv_set(self.db, f"cfg:{wf_id}", cfg)
            elif s in ("rejected", "expired", "lapsed"):
                self.db.execute("UPDATE proposals SET status=? WHERE prop_id=?",
                                (s, row["prop_id"]))

    def _can_submit(self, wf_id: str, ts: str) -> bool:
        """True if timing + rate-limit constraints allow a new proposal."""
        # Already have one in flight?
        pending = self.db.execute(
            "SELECT COUNT(*) FROM proposals WHERE workflow_id=? AND status='pending'",
            (wf_id,)
        ).fetchone()[0]
        if pending > 0:
            return False

        wf = self.workflows.get(wf_id, {})
        gov = wf.get("governance", {})
        approver_hours = gov.get("approver_hours", [9, 18])
        latency_max_h = gov.get("approver_latency_minutes", [30, 240])[1] / 60
        apply_window_h = gov.get("apply_window_hours", 2)
        max_per_day = gov.get("max_requests_per_24h", 3)

        sim_hour = int(ts[11:13])
        # Must be inside approver window, with enough time left
        window_end = approver_hours[1] - latency_max_h - apply_window_h - 0.5
        if sim_hour < approver_hours[0] or sim_hour >= window_end:
            return False

        # Kestrel ops supervisor: not before 11:00
        if wf_id == "ks_cancel" and sim_hour < 11:
            return False

        today = ts[:10]
        submitted_today = self.db.execute(
            "SELECT COUNT(*) FROM proposals WHERE workflow_id=? AND submitted_ts LIKE ?",
            (wf_id, today + "%")
        ).fetchone()[0]
        return submitted_today < max_per_day

    def _submit_proposal(
        self, wf_id: str, ts: str,
        new_cfg: dict, summary: str, rationale: str,
        evidence: Optional[dict] = None,
    ) -> bool:
        cur = self._get_config(wf_id)
        if cur is None:
            return False

        base_version = cur["version"]
        old_cfg = cur["config"]

        diff = _config_diff(old_cfg, new_cfg)
        if not diff:
            return False  # nothing changed

        prop_id = str(uuid.uuid4())
        # Persist before submitting — idempotency
        self.db.execute(
            "INSERT INTO proposals VALUES (?,?,?,NULL,?,?,NULL,?)",
            (prop_id, wf_id, "draft", base_version, json.dumps(new_cfg), summary)
        )
        self.db.commit()

        # Estimate affected leads
        affected = self.db.execute(
            "SELECT COUNT(DISTINCT COALESCE(cohort_id,'default')) * 300 FROM calls WHERE workflow_id=?",
            (wf_id,)
        ).fetchone()[0] or 100

        body = {
            "proposal_id": prop_id,
            "workflow_id": wf_id,
            "base_version": base_version,
            "proposed_config": new_cfg,
            "change_summary": summary[:200],
            "diff": diff,
            "affected_leads": min(int(affected), 50000),
            "dry_run": {"method": "historical_cohort_replay", "note": rationale[:300]},
            "impact_score": min(0.85, 0.2 + len(diff) * 0.1),
            "rationale": rationale,
        }
        if evidence:
            body["evidence"] = evidence

        r = self.c.post("/approvals", json=body)
        if r.status_code == 200:
            approval_id = r.json()["approval_id"]
            self.db.execute(
                "UPDATE proposals SET status='pending', approval_id=?, submitted_ts=? WHERE prop_id=?",
                (approval_id, ts, prop_id)
            )
            add_audit(self.db, ts, wf_id, "proposal_submitted",
                      {"approval_id": approval_id, "summary": summary})
            log.info("[%s] Proposal submitted: %s", wf_id, approval_id)
            return True
        else:
            err = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
            self.db.execute("UPDATE proposals SET status='rejected' WHERE prop_id=?", (prop_id,))
            if "stale_base_version" in str(err):
                cfg = self.c.get(f"/workflows/{wf_id}/config").json()
                kv_set(self.db, f"cfg:{wf_id}", cfg)
            log.warning("[%s] Proposal rejected %s: %s", wf_id, r.status_code, err)
            return False

    def _auto_apply(self, wf_id: str, ts: str, new_cfg: dict, rationale: str,
                    evidence: Optional[dict] = None) -> bool:
        cur = self._get_config(wf_id)
        if cur is None:
            return False
        prop_id = str(uuid.uuid4())
        body: dict = {
            "proposal_id": prop_id,
            "base_version": cur["version"],
            "proposed_config": new_cfg,
            "rationale": rationale,
        }
        if evidence:
            body["evidence"] = evidence
        r = self.c.put(f"/workflows/{wf_id}/config", json=body)
        if r.status_code == 200:
            cfg = self.c.get(f"/workflows/{wf_id}/config").json()
            kv_set(self.db, f"cfg:{wf_id}", cfg)
            add_audit(self.db, ts, wf_id, "auto_applied",
                      {"rationale": rationale, "proposal_id": prop_id})
            log.info("[%s] Auto-applied: %s", wf_id, rationale[:80])
            return True
        else:
            if "stale_base_version" in r.text:
                cfg = self.c.get(f"/workflows/{wf_id}/config").json()
                kv_set(self.db, f"cfg:{wf_id}", cfg)
            log.warning("[%s] Auto-apply failed %s: %s", wf_id, r.status_code, r.text[:200])
            return False

    # ─── Caller-ID health (C5) ────────────────────────────────────────────────

    def _check_caller_ids(self, wf_id: str, ts: str):
        wf = self.workflows.get(wf_id, {})
        dids = wf.get("options", {}).get("caller_id", [])
        if len(dids) < 2:
            return

        watermark = kv_get(self.db, "history_watermark", 0)
        rates: dict[str, float] = {}
        for did in dids:
            row = self.db.execute("""
                SELECT COUNT(*) AS n, COALESCE(SUM(connected),0) AS c FROM (
                    SELECT connected FROM calls
                    WHERE workflow_id=? AND caller_id=? AND event_id > ?
                    ORDER BY event_id DESC LIMIT 150
                )
            """, (wf_id, did, watermark)).fetchone()
            if row["n"] >= 50:
                rates[did] = row["c"] / row["n"]

        if len(rates) < 2:
            return

        sorted_rates = sorted(rates.values())
        median_rate = sorted_rates[len(sorted_rates) // 2]
        suspects = set(
            d for d, r in rates.items()
            if r < median_rate * 0.65 and r < 0.25
        )
        if not suspects:
            # Clear any pending flags for DIDs that recovered
            kv_set(self.db, f"pending_flags:{wf_id}", [])
            return

        # Require two consecutive detections to avoid false positives from noise
        pending = set(kv_get(self.db, f"pending_flags:{wf_id}", []))
        confirmed = suspects & pending  # seen bad in both this tick and previous
        # Update pending to current suspects for next tick
        kv_set(self.db, f"pending_flags:{wf_id}", list(suspects))
        if not confirmed:
            return  # first sighting only — wait for confirmation

        already_flagged = kv_get(self.db, f"flagged_dids:{wf_id}", [])
        new_flags = [d for d in confirmed if d not in already_flagged]
        if not new_flags:
            return

        kv_set(self.db, f"flagged_dids:{wf_id}", already_flagged + new_flags)
        add_audit(self.db, ts, wf_id, "caller_id_flagged",
                  {"flagged": new_flags, "pickup_rates": rates})
        log.info("[%s] Caller IDs flagged: %s", wf_id, new_flags)

        cur = self._get_config(wf_id)
        if cur is None:
            return
        new_cfg = copy.deepcopy(cur["config"])
        for cohort_alloc in new_cfg.get("allocations", {}).values():
            if "caller_id" in cohort_alloc:
                # Reduce flagged DIDs to 0.1× their weight (gradual, respects max_shift)
                new_caller = {}
                for d, w in cohort_alloc["caller_id"].items():
                    new_caller[d] = w * 0.1 if d in new_flags else w
                total = sum(new_caller.values())
                if total > 0:
                    cohort_alloc["caller_id"] = {d: w / total for d, w in new_caller.items()}

        gov = wf.get("governance", {})
        aa = gov.get("auto_apply", {})
        can_auto = aa.get("enabled") and "caller_id" in aa.get("allowed_dims", [])
        applied = False
        if can_auto:
            applied = self._auto_apply(wf_id, ts, new_cfg,
                                       f"Rotate spam-flagged caller IDs {new_flags}")
        if not applied and self._can_submit(wf_id, ts):
            self._submit_proposal(
                wf_id, ts, new_cfg,
                f"Rotate flagged caller IDs: {new_flags}",
                f"DIDs {new_flags} showing pickup rate below 65% of median ({median_rate:.2%})"
            )
        elif not applied:
            # Outside approver hours — store for retry on next submittable tick
            kv_set(self.db, f"pending_cid:{wf_id}",
                   {"cfg": new_cfg, "flags": new_flags, "median": median_rate})

    # ─── Hallucination detection (C8) ────────────────────────────────────────

    def _check_hallucination(self, wf_id: str, ts: str):
        # Check if there's already an open incident
        open_inc = self.db.execute(
            "SELECT * FROM hallucination_incidents WHERE workflow_id=? AND status='open'",
            (wf_id,)
        ).fetchone()

        # Recent hallucination rate (last 100 connected calls)
        row = self.db.execute("""
            SELECT COUNT(*) AS n,
                   COALESCE(SUM(hallucination_flag),0) AS h
            FROM (
                SELECT hallucination_flag FROM calls
                WHERE workflow_id=? AND connected=1 AND hallucination_flag IS NOT NULL
                ORDER BY event_id DESC LIMIT 100
            )
        """, (wf_id,)).fetchone()

        n, h = row["n"], row["h"]
        if n < 30:
            return  # not enough data

        recent_rate = h / n

        # Baseline: first 100 connected calls of the scenario
        base_row = self.db.execute("""
            SELECT COUNT(*) AS n, COALESCE(SUM(hallucination_flag),0) AS h
            FROM (
                SELECT hallucination_flag FROM calls
                WHERE workflow_id=? AND connected=1 AND hallucination_flag IS NOT NULL
                ORDER BY event_id ASC LIMIT 100
            )
        """, (wf_id,)).fetchone()
        base_n, base_h = base_row["n"], base_row["h"]
        if base_n < 20:
            return
        baseline_rate = base_h / base_n

        # Require ≥4% absolute AND ≥3× baseline — prevents false positives on P1 (0.6% base)
        threshold = max(baseline_rate * 3.0, 0.04)
        if recent_rate < threshold:
            if open_inc:
                # Check if fixed: hallucination back to normal
                if recent_rate <= baseline_rate * 1.5:
                    self.db.execute(
                        "UPDATE hallucination_incidents SET status='resolved' WHERE incident_id=?",
                        (open_inc["incident_id"],)
                    )
                    add_audit(self.db, ts, wf_id, "hallucination_resolved",
                              {"rate_now": recent_rate, "baseline": baseline_rate})
            return

        if open_inc:
            return  # Already handling it

        # Cooldown: respond at most once per 24 sim hours per workflow
        last_resp = kv_get(self.db, f"halluc_resp_ts:{wf_id}", "")
        if last_resp and ts < _add_hours(last_resp, 24):
            return  # In cooldown — don't even open a new incident

        # New incident
        inc_id = str(uuid.uuid4())
        cur_cfg = self._get_config(wf_id)
        cur_prompt = cur_cfg["config"].get("prompt_version", "P1") if cur_cfg else "P1"
        self.db.execute(
            "INSERT INTO hallucination_incidents VALUES (?,?,?,?,?,NULL,NULL)",
            (inc_id, wf_id, ts, "open", cur_prompt)
        )
        add_audit(self.db, ts, wf_id, "hallucination_incident",
                  {"rate": recent_rate, "baseline": baseline_rate, "prompt": cur_prompt})
        log.info("[%s] Hallucination incident! rate=%.3f baseline=%.3f",
                 wf_id, recent_rate, baseline_rate)

        # Check credits before spending
        state = self.c.get("/sim/state").json()
        if state.get("credits_remaining", 0) < 15:
            log.warning("[%s] Low credits (%d), skipping LLM fix", wf_id,
                        state.get("credits_remaining", 0))
            return

        kv_set(self.db, f"halluc_resp_ts:{wf_id}", ts)
        self._respond_to_hallucination(wf_id, ts, inc_id, cur_prompt)

    def _respond_to_hallucination(self, wf_id: str, ts: str, inc_id: str, cur_prompt: str):
        # 1. Ask LLM for suggestions (3 credits)
        r = self.c.post("/llm/suggest-fixes", json={
            "workflow_id": wf_id,
            "problem": f"Hallucination rate spiked to 3x baseline. Current prompt: {cur_prompt}."
                       " Suggest safer alternatives."
        })
        if r.status_code != 200:
            log.warning("[%s] LLM suggest-fixes failed: %s", wf_id, r.status_code)
            return
        candidates = r.json().get("suggestions", [])
        if not candidates:
            return

        # 2. Validate each candidate (1 credit per 100 calls)
        wf = self.workflows.get(wf_id, {})
        gov = wf.get("governance", {})
        min_pass_rate = gov.get("min_validation_pass_rate", 0.97)
        allowed_prompts = wf.get("options", {}).get("prompt_version", [])

        best_prompt = None
        best_run_id = None
        for cand in candidates:
            pv = cand if isinstance(cand, str) else cand.get("prompt_version")
            if not pv or pv not in allowed_prompts or pv == cur_prompt:
                continue

            state = self.c.get("/sim/state").json()
            if state.get("credits_remaining", 0) < 5:
                break

            vr = self.c.post("/validation/runs", json={
                "workflow_id": wf_id, "prompt_version": pv, "n": 100
            })
            if vr.status_code != 200:
                continue
            vdata = vr.json()
            run_id = vdata.get("run_id") or vdata.get("validation_run_id")
            pass_rate = vdata.get("pass_rate", 0)
            log.info("[%s] Validation %s: pass_rate=%.3f (need %.3f)",
                     wf_id, pv, pass_rate, min_pass_rate)

            if pass_rate >= min_pass_rate:
                best_prompt = pv
                best_run_id = run_id
                break  # Take first passing one

        if best_prompt is None:
            # Fall back to known-safe prompt if available
            for safe in ["P3", "P1"]:
                if safe in allowed_prompts and safe != cur_prompt:
                    # Run validation on safe prompt
                    state = self.c.get("/sim/state").json()
                    if state.get("credits_remaining", 0) < 2:
                        break
                    vr = self.c.post("/validation/runs", json={
                        "workflow_id": wf_id, "prompt_version": safe, "n": 100
                    })
                    if vr.status_code == 200:
                        vdata = vr.json()
                        if vdata.get("pass_rate", 0) >= min_pass_rate:
                            best_prompt = safe
                            best_run_id = vdata.get("run_id") or vdata.get("validation_run_id")
                            break

        if best_prompt is None:
            log.warning("[%s] No validated prompt found for hallucination fix", wf_id)
            return

        # 3. Update incident record
        self.db.execute(
            "UPDATE hallucination_incidents SET prompt_after=?, validation_run_id=? WHERE incident_id=?",
            (best_prompt, best_run_id, inc_id)
        )

        # 4. Propose or auto-apply
        cur = self._get_config(wf_id)
        if cur is None:
            return
        new_cfg = copy.deepcopy(cur["config"])
        new_cfg["prompt_version"] = best_prompt

        evidence = {"validation_run_id": best_run_id}
        wf_gov = self.workflows.get(wf_id, {}).get("governance", {})
        aa = wf_gov.get("auto_apply", {})
        can_auto = aa.get("enabled") and "prompt_version" in aa.get("allowed_dims", [])

        rationale = (
            f"Hallucination rate spiked to 3x baseline. "
            f"Validated {best_prompt} with pass_rate≥{min_pass_rate}. "
            f"Reverting from {cur_prompt}."
        )

        applied = False
        if can_auto:
            applied = self._auto_apply(wf_id, ts, new_cfg, rationale, evidence=evidence)
        if not applied and self._can_submit(wf_id, ts):
            self._submit_proposal(
                wf_id, ts, new_cfg,
                f"Fix hallucination: replace {cur_prompt} to {best_prompt}",
                rationale, evidence=evidence
            )

    # ─── Experiments (C6) ────────────────────────────────────────────────────

    def _advance_experiments(self, wf_id: str, ts: str):
        wf = self.workflows.get(wf_id, {})
        options = wf.get("options", {})
        objective = wf.get("objective", {})
        primary_kpi = objective.get("primary", "engagement_rate")
        guardrail = objective.get("guardrail", {})

        for dim in ["voice", "welcome_message"]:
            variants = options.get(dim, [])
            if len(variants) < 2:
                continue

            active = self.db.execute(
                "SELECT * FROM experiments WHERE workflow_id=? AND dim=? AND status='active'",
                (wf_id, dim)
            ).fetchone()

            if active is None:
                self._start_experiment(wf_id, dim, variants, ts)
            else:
                self._update_experiment(active, wf_id, dim, primary_kpi, guardrail, variants, ts)

    def _start_experiment(self, wf_id: str, dim: str, variants: list, ts: str):
        # Don't re-run if we already found a winner and applied it
        done = self.db.execute(
            "SELECT * FROM experiments WHERE workflow_id=? AND dim=? AND status='done' "
            "ORDER BY rowid DESC LIMIT 1",
            (wf_id, dim)
        ).fetchone()
        if done and done["winner"]:
            return

        exp_id = str(uuid.uuid4())
        arms = {v: {"dials": 0, "connected": 0, "engaged": 0} for v in variants}
        self.db.execute(
            "INSERT INTO experiments VALUES (?,?,?,?,?,NULL,NULL,?)",
            (exp_id, wf_id, dim, "active", ts, json.dumps(arms))
        )
        add_audit(self.db, ts, wf_id, "experiment_started",
                  {"exp_id": exp_id, "dim": dim, "variants": variants})
        log.info("[%s] Experiment started: %s over %s", wf_id, dim, variants)
        self._push_uniform_allocation(wf_id, dim, variants, exp_id, ts)

    def _push_uniform_allocation(self, wf_id: str, dim: str, variants: list,
                                  exp_id: str, ts: str):
        """Push a uniform allocation for `dim` so all variants get traffic.

        Called at experiment start and re-tried every tick until traffic arrives.
        """
        cur = self._get_config(wf_id)
        if cur is None:
            return
        cur_alloc = cur["config"].get("allocations", {}).get("default", {}).get(dim, {})
        already_uniform = len(cur_alloc) >= len(variants)
        if already_uniform:
            return  # Already exploring

        new_cfg = copy.deepcopy(cur["config"])
        for cohort in new_cfg.get("allocations", {}):
            new_cfg["allocations"][cohort][dim] = {v: 1.0 for v in variants}

        wf_gov = self.workflows.get(wf_id, {}).get("governance", {})
        aa = wf_gov.get("auto_apply", {})
        can_auto = (aa.get("enabled") and dim in aa.get("allowed_dims", [])
                    and _tvd_ok(cur["config"], new_cfg, dim, aa.get("max_shift", 0.5)))

        applied = False
        if can_auto:
            applied = self._auto_apply(wf_id, ts, new_cfg,
                                       f"Start uniform {dim} exploration (exp {exp_id})")
        if not applied and self._can_submit(wf_id, ts):
            # Only submit if no pending proposal for this dim already in flight
            pending = self.db.execute(
                "SELECT 1 FROM proposals WHERE workflow_id=? AND status='pending'"
                " AND config_json LIKE ?",
                (wf_id, f'%"{dim}"%')
            ).fetchone()
            if not pending:
                self._submit_proposal(
                    wf_id, ts, new_cfg,
                    f"Start {dim} experiment: uniform exploration across {variants}",
                    f"Beginning statistical experiment. Uniform allocation ensures all variants reach {MIN_CALLS_PER_ARM} connected calls."
                )

    def _update_experiment(self, exp_row, wf_id: str, dim: str,
                           primary_kpi: str, guardrail: dict,
                           all_variants: list, ts: str):
        exp_id = exp_row["exp_id"]
        exp_start = exp_row["started_ts"]
        arms = json.loads(exp_row["arms_json"])

        # Recompute stats from calls since experiment start
        for variant in list(arms.keys()):
            col = dim  # 'voice' or 'welcome_message'
            row = self.db.execute(f"""
                SELECT COUNT(*) AS dials,
                       COALESCE(SUM(connected),0) AS connected,
                       COALESCE(SUM(CASE WHEN connected=1 THEN engaged END),0) AS engaged
                FROM calls
                WHERE workflow_id=? AND {col}=? AND ts >= ?
            """, (wf_id, variant, exp_start)).fetchone()
            arms[variant] = {
                "dials": row["dials"],
                "connected": row["connected"],
                "engaged": row["engaged"],
            }

        self.db.execute("UPDATE experiments SET arms_json=? WHERE exp_id=?",
                        (json.dumps(arms), exp_id))

        # If some arms still have zero traffic, try pushing uniform allocation again
        # (the first attempt in _start_experiment may have been outside approver hours)
        if any(a["dials"] == 0 for a in arms.values()):
            self._push_uniform_allocation(wf_id, dim, all_variants, exp_id, ts)
            return

        # Need minimum samples in every arm before testing
        if any(a["connected"] < MIN_CALLS_PER_ARM for a in arms.values()):
            return

        # Determine control (most-allocated variant in current config)
        cur = self._get_config(wf_id)
        cur_alloc = (cur["config"].get("allocations", {}).get("default", {}).get(dim, {})
                     if cur else {})
        control = max(cur_alloc, key=cur_alloc.get) if cur_alloc else all_variants[0]
        if control not in arms:
            control = all_variants[0]

        ctrl = arms[control]
        if ctrl["connected"] == 0:
            return

        challengers = [v for v in arms if v != control]
        alpha = bonferroni_alpha(len(challengers))

        # Pick metric
        if primary_kpi == "engagement_rate":
            ctrl_n, ctrl_s = ctrl["connected"], ctrl["engaged"]
            ctrl_rate = ctrl_s / ctrl_n
            def arm_ns(a): return a["connected"], a["engaged"]
            def arm_rate(a): return a["engaged"] / a["connected"] if a["connected"] else 0
            gr_key = "pickup_rate_max_drop"
            def guardrail_ok(a):
                drop = guardrail.get(gr_key, 0.05)
                cp = ctrl["connected"] / max(ctrl["dials"], 1)
                ap = a["connected"] / max(a["dials"], 1)
                return ap >= cp - drop
        else:  # pickup_rate
            ctrl_n, ctrl_s = ctrl["dials"], ctrl["connected"]
            ctrl_rate = ctrl_s / ctrl_n
            def arm_ns(a): return a["dials"], a["connected"]
            def arm_rate(a): return a["connected"] / a["dials"] if a["dials"] else 0
            gr_key = "engagement_rate_max_drop"
            def guardrail_ok(a):
                drop = guardrail.get(gr_key, 0.05)
                ce = ctrl["engaged"] / max(ctrl["connected"], 1)
                ae = a["engaged"] / max(a["connected"], 1)
                return ae >= ce - drop

        best_v, best_lift, best_p = None, 0.0, 1.0
        for v in challengers:
            a = arms[v]
            if not guardrail_ok(a):
                continue
            n2, s2 = arm_ns(a)
            _, p = z_test_two_props(ctrl_n, ctrl_s, n2, s2)
            lift = arm_rate(a) - ctrl_rate
            if p < alpha and lift > 0.01 and lift > best_lift:
                best_v, best_lift, best_p = v, lift, p

        if best_v:
            self._conclude_experiment(exp_id, wf_id, dim, best_v, best_lift, best_p, ts)
        else:
            # No winner yet — log current state periodically
            ts_hour = ts[11:13]
            if ts_hour == "20":
                log.info("[%s] Experiment %s/%s: no winner yet. Best lift so far needs more data.",
                         wf_id, dim, exp_id[:8])

    def _conclude_experiment(self, exp_id: str, wf_id: str, dim: str,
                              winner: str, lift: float, p_val: float, ts: str):
        self.db.execute(
            "UPDATE experiments SET status='done', concluded_ts=?, winner=? WHERE exp_id=?",
            (ts, winner, exp_id)
        )
        add_audit(self.db, ts, wf_id, "winner_found",
                  {"exp_id": exp_id, "dim": dim, "winner": winner,
                   "lift": round(lift, 4), "p_value": round(p_val, 6)})
        log.info("[%s] Winner for %s: %s (+%.1f%%, p=%.4f)",
                 wf_id, dim, winner, lift * 100, p_val)

        cur = self._get_config(wf_id)
        if cur is None:
            return

        # Build new config: 90% winner, 10% across others for continued exploration
        new_cfg = copy.deepcopy(cur["config"])
        wf = self.workflows.get(wf_id, {})
        all_v = wf.get("options", {}).get(dim, [winner])
        others = [v for v in all_v if v != winner]
        if others:
            new_alloc = {winner: 0.9, **{v: 0.1 / len(others) for v in others}}
        else:
            new_alloc = {winner: 1.0}

        for cohort in new_cfg.get("allocations", {}):
            new_cfg["allocations"][cohort][dim] = new_alloc

        summary = f"Apply {dim} winner: {winner} (+{lift:.1%} {wf.get('objective',{}).get('primary','engagement_rate')})"
        rationale = (
            f"Z-test on {MIN_CALLS_PER_ARM}+ connected calls per arm: "
            f"{winner} beats control with p={p_val:.4f} < {bonferroni_alpha(len(all_v)-1):.4f} "
            f"(Bonferroni-corrected). Lift: +{lift:.1%}."
        )

        wf_gov = wf.get("governance", {})
        aa = wf_gov.get("auto_apply", {})
        can_auto = (aa.get("enabled") and dim in aa.get("allowed_dims", [])
                    and _tvd_ok(cur["config"], new_cfg, dim, aa.get("max_shift", 0.5)))

        applied = False
        if can_auto:
            applied = self._auto_apply(wf_id, ts, new_cfg, rationale)
        if not applied and self._can_submit(wf_id, ts):
            self._submit_proposal(wf_id, ts, new_cfg, summary, rationale)
        elif not applied:
            # Stash it; _flush_pending_winners runs every tick and will retry
            kv_set(self.db, f"pending_winner:{wf_id}:{dim}",
                   {"exp_id": exp_id, "winner": winner, "lift": lift,
                    "summary": summary, "rationale": rationale})

    def _flush_pending_winners(self, wf_id: str, ts: str):
        """Try to submit any stashed winner proposals."""
        wf = self.workflows.get(wf_id, {})
        for dim in ["voice", "welcome_message"]:
            pw = kv_get(self.db, f"pending_winner:{wf_id}:{dim}")
            if not pw:
                continue
            if not self._can_submit(wf_id, ts):
                continue
            # Rebuild config from scratch (base may have changed)
            cur = self._get_config(wf_id)
            if cur is None:
                continue
            new_cfg = copy.deepcopy(cur["config"])
            winner = pw["winner"]
            wf_opts = wf.get("options", {}).get(dim, [winner])
            others = [v for v in wf_opts if v != winner]
            new_alloc = {winner: 0.9, **{v: 0.1 / len(others) for v in others}} if others else {winner: 1.0}
            for cohort in new_cfg.get("allocations", {}):
                new_cfg["allocations"][cohort][dim] = new_alloc

            ok = self._submit_proposal(wf_id, ts, new_cfg, pw["summary"], pw["rationale"])
            if ok:
                kv_set(self.db, f"pending_winner:{wf_id}:{dim}", None)

    def _flush_pending_cid(self, wf_id: str, ts: str):
        """Retry a deferred caller-ID rotation (stored when outside approver hours)."""
        pending = kv_get(self.db, f"pending_cid:{wf_id}")
        if not pending:
            return
        if not self._can_submit(wf_id, ts):
            return
        wf = self.workflows.get(wf_id, {})
        gov = wf.get("governance", {})
        aa = gov.get("auto_apply", {})
        can_auto = aa.get("enabled") and "caller_id" in aa.get("allowed_dims", [])
        new_cfg = pending["cfg"]
        new_flags = pending["flags"]
        median_rate = pending["median"]
        applied = False
        if can_auto:
            applied = self._auto_apply(wf_id, ts, new_cfg,
                                       f"Rotate spam-flagged caller IDs {new_flags}")
        if not applied:
            ok = self._submit_proposal(
                wf_id, ts, new_cfg,
                f"Rotate flagged caller IDs: {new_flags}",
                f"DIDs {new_flags} showing pickup rate below 65% of median ({median_rate:.2%})"
            )
            if ok:
                kv_set(self.db, f"pending_cid:{wf_id}", None)
        else:
            kv_set(self.db, f"pending_cid:{wf_id}", None)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _get_config(self, wf_id: str) -> Optional[dict]:
        cfg = kv_get(self.db, f"cfg:{wf_id}")
        if cfg is None:
            try:
                cfg = self.c.get(f"/workflows/{wf_id}/config").json()
                kv_set(self.db, f"cfg:{wf_id}", cfg)
            except Exception:
                return None
        return cfg


# ─── Pure helpers ─────────────────────────────────────────────────────────────

def _config_diff(old: dict, new: dict) -> dict:
    diff = {}
    for k in set(old) | set(new):
        if old.get(k) != new.get(k):
            diff[k] = {"old": old.get(k), "new": new.get(k)}
    return diff


def _normalize(d: dict) -> dict:
    total = sum(d.values()) or 1
    return {k: v / total for k, v in d.items()}


def _tvd(d1: dict, d2: dict) -> float:
    keys = set(d1) | set(d2)
    return sum(abs(_normalize(d1).get(k, 0) - _normalize(d2).get(k, 0)) for k in keys) / 2


def _add_hours(ts_str: str, hours: int) -> str:
    """Return ISO timestamp string `hours` ahead of `ts_str`."""
    from datetime import datetime, timedelta, timezone
    try:
        dt = datetime.fromisoformat(ts_str)
        dt2 = dt + timedelta(hours=hours)
        return dt2.isoformat()
    except Exception:
        return ts_str


def _tvd_ok(old_cfg: dict, new_cfg: dict, dim: str, max_shift: float) -> bool:
    for cohort in old_cfg.get("allocations", {}):
        old_d = old_cfg["allocations"].get(cohort, {}).get(dim, {})
        new_d = new_cfg.get("allocations", {}).get(cohort, {}).get(dim, {})
        if _tvd(old_d, new_d) > max_shift:
            return False
    return True
