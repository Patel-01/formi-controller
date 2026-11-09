# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.348 | +4.5% | 0.239 | +0.3% | 0.508 | +3.6% | 15% | 65 (47) |
| nw_kyc | 0.353 | -2.8% | 0.238 | -1.8% | 0.591 | +0.1% | 0% | 26 (21) |
| nw_renewal | 0.443 | +5.6% | 0.264 | +0.2% | 0.575 | +5.5% | 27% | 108 (42) |
| ALL | 0.381 | +3.4% | 0.247 | -0.1% | 0.548 | +3.5% | 16% | 199 (110) |

## Changes applied by the controller

10 applied — beneficial: 6, neutral: 3, harmful: 1

- ks_cancel v2 (controller_approved) dims=['voice'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**
- nw_renewal v2 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- ks_cancel v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.023 didΔ=+0.000 → **harmful**
- nw_renewal v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.065 didΔ=+0.000 → **beneficial**
- ks_cancel v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.002 → **neutral**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.081 → **beneficial**
- ks_cancel v5 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.120 → **beneficial**
- ks_cancel v6 (controller_approved) dims=['voice'] engageΔ=+0.052 didΔ=+0.000 → **beneficial**
- nw_renewal v6 (controller_approved) dims=['prompt_version'] engageΔ=+0.049 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 9,
  "decisions": {
    "approved": 8,
    "rejected": 1,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 8,
  "auto_applied": 2,
  "auto_apply_rejected": 4,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 1,
    "ks_cancel": 2
  }
}
```

## Incidents

```
[]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:welcome_message=W3": {
    "4": 0.325,
    "5": 0.334,
    "6": 0.338,
    "7": 0.327
  }
}
```

Credits used: 49 · validation runs: 13 · LLM fix calls: 12