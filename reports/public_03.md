# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.364 | +6.7% | 0.244 | -0.0% | 0.530 | +5.9% | 42% | 397 (408) |
| arav_kyc_1 | 0.356 | +0.5% | 0.215 | +0.1% | 0.597 | +0.2% | 0% | 322 (370) |
| arav_renewal_0 | 0.441 | +9.6% | 0.264 | +0.0% | 0.593 | +9.2% | 46% | 399 (440) |
| kest_cancel_2 | 0.370 | +9.2% | 0.243 | -0.2% | 0.541 | +8.6% | 61% | 385 (411) |
| kest_kyc_1 | 0.356 | +0.9% | 0.215 | +0.7% | 0.594 | -0.0% | 0% | 328 (339) |
| kest_renewal_0 | 0.441 | +10.3% | 0.263 | -0.3% | 0.592 | +9.3% | 45% | 441 (433) |
| nort_cancel_2 | 0.375 | +10.6% | 0.245 | +1.1% | 0.540 | +8.2% | 54% | 778 (393) |
| nort_kyc_1 | 0.354 | +0.1% | 0.214 | +0.4% | 0.598 | +0.4% | 0% | 331 (323) |
| nort_renewal_0 | 0.442 | +9.1% | 0.264 | +0.1% | 0.596 | +8.9% | 46% | 433 (411) |
| tide_cancel_2 | 0.368 | +8.6% | 0.243 | -0.5% | 0.538 | +7.7% | 48% | 387 (407) |
| tide_kyc_1 | 0.354 | +0.2% | 0.214 | -0.1% | 0.592 | -0.0% | 0% | 348 (356) |
| tide_renewal_0 | 0.430 | +7.2% | 0.263 | -0.6% | 0.583 | +7.5% | 38% | 423 (438) |
| ALL | 0.388 | +6.2% | 0.241 | +0.0% | 0.574 | +5.6% | 31% | 4972 (4729) |

## Changes applied by the controller

37 applied — beneficial: 23, neutral: 9, harmful: 5

- kest_cancel_2 v2 (controller_approved) dims=['voice'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**
- tide_cancel_2 v2 (controller_approved) dims=['voice'] engageΔ=+0.021 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v2 (controller_approved) dims=['voice'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v2 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- nort_renewal_0 v2 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- tide_renewal_0 v2 (controller_approved) dims=['voice'] engageΔ=+0.001 didΔ=+0.000 → **neutral**
- tide_cancel_2 v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.023 didΔ=+0.000 → **harmful**
- arav_cancel_2 v2 (controller_approved) dims=['voice'] engageΔ=+0.021 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.023 didΔ=+0.000 → **harmful**
- arav_renewal_0 v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.066 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.023 didΔ=+0.000 → **harmful**
- tide_renewal_0 v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.066 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.066 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v2 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- kest_cancel_2 v4 (controller_approved) dims=['voice'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.023 didΔ=+0.000 → **harmful**
- kest_cancel_2 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.046 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v4 (controller_approved) dims=['voice'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.066 didΔ=+0.000 → **beneficial**
- tide_cancel_2 v4 (controller_approved) dims=['voice'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.065 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.065 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v4 (controller_approved) dims=['voice'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v4 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- tide_cancel_2 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.046 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.065 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.046 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.046 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v6 (controller_approved) dims=['prompt_version'] engageΔ=+0.031 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.065 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v5 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- kest_renewal_0 v5 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nort_cancel_2 v6 (controller_approved) dims=['prompt_version'] engageΔ=+0.050 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v7 (controller_approved) dims=['prompt_version'] engageΔ=-0.030 didΔ=+0.000 → **harmful**
- kest_cancel_2 v8 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.001 → **neutral**
- nort_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.000 → **neutral**
- nort_renewal_0 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.031 → **beneficial**

## Governance

```
{
  "approval_requests": 35,
  "decisions": {
    "approved": 35,
    "expired": 0
  },
  "rejection_reasons": {},
  "applied_via_approval": 35,
  "auto_applied": 2,
  "auto_apply_rejected": 4,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nort_renewal_0": 2,
    "nort_cancel_2": 2,
    "kest_renewal_0": 2,
    "kest_cancel_2": 3,
    "arav_renewal_0": 2,
    "arav_cancel_2": 2,
    "tide_renewal_0": 2,
    "tide_cancel_2": 2
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
  "nort_renewal_0:welcome_message=W3": {
    "3": 0.901,
    "4": 0.898
  },
  "arav_renewal_0:welcome_message=W3": {
    "3": 0.9,
    "4": 0.901
  },
  "tide_renewal_0:welcome_message=W3": {
    "3": 0.897,
    "4": 0.9
  },
  "kest_renewal_0:welcome_message=W3": {
    "4": 0.899
  }
}
```

Credits used: 90 · validation runs: 24 · LLM fix calls: 22