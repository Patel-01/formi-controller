# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.270 | +9.0% | 0.202 | +9.7% | 0.470 | -1.4% | 22% | 400 (330) |
| nw_kyc | 0.376 | +0.4% | 0.244 | +0.9% | 0.589 | -0.5% | 0% | 30 (31) |
| nw_renewal | 0.418 | -2.1% | 0.259 | -0.9% | 0.539 | -1.6% | -13% | 56 (55) |
| ALL | 0.342 | +2.2% | 0.230 | +3.6% | 0.521 | -1.6% | 6% | 486 (416) |

## Changes applied by the controller

11 applied — harmful: 2, neutral: 2, beneficial: 7

- nw_renewal v2 (controller_approved) dims=['voice'] engageΔ=-0.018 didΔ=+0.000 → **harmful**
- ks_cancel v2 (controller_approved) dims=['voice'] engageΔ=+0.008 didΔ=+0.000 → **neutral**
- ks_cancel v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- nw_renewal v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.002 → **neutral**
- ks_cancel v4 (controller_approved) dims=['prompt_version'] engageΔ=+0.031 didΔ=+0.000 → **beneficial**
- nw_renewal v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.060 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.396 → **beneficial**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.133 → **beneficial**
- ks_cancel v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.027 didΔ=+0.000 → **beneficial**
- nw_renewal v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.095 didΔ=+0.000 → **beneficial**
- nw_renewal v8 (controller_approved) dims=['voice'] engageΔ=-0.044 didΔ=+0.000 → **harmful**

## Governance

```
{
  "approval_requests": 12,
  "decisions": {
    "approved": 10,
    "rejected": 2,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 2
  },
  "applied_via_approval": 9,
  "auto_applied": 2,
  "auto_apply_rejected": 2,
  "apply_conflicts": 1,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 2,
    "ks_cancel": 2
  }
}
```

## Incidents

```
[
  {
    "type": "did_flagged",
    "workflow": "ks_cancel",
    "at": "D2 10:00",
    "flagged_did_share_by_day": {
      "2": 0.186,
      "3": 0.088,
      "4": 0.086,
      "5": 0.092,
      "6": 0.094,
      "7": 0.092,
      "8": 0.092,
      "9": 0.094
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D3 11:30",
    "mttr_minutes": null,
    "fixed_by": null
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D5 15:00"
  }
]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:welcome_message=W3": {
    "4": 0.901,
    "5": 0.898,
    "6": 0.898,
    "7": 0.903,
    "8": 0.899,
    "9": 0.901
  }
}
```

Credits used: 70 · validation runs: 19 · LLM fix calls: 17