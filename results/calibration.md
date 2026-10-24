Calibration of the density score for adaptive_hold: 14 candidates on tuning seeds 1001-1002, finalists on held-out seeds 1-10.

Best candidate on the tuning seeds (objective = mean delay relative to hand-set, averaged over conditions): 0.943 (hand-set 1.000, plain count 1.169).

| Parameter | Hand-set | Calibrated |
|---|---|---|
| motorcycle | 0.50 | 1.89 |
| auto | 0.80 | 3.02 |
| bus | 3.00 | 1.67 |
| truck | 2.50 | 0.93 |
| emergency | 6.00 | 1.91 |
| queued_ratio | 3.00 | 2.94 |
| theta | 1.10 | 1.37 |

Held-out evaluation (mean delay, s):

| Score | medium | high | 0.9x capacity |
|---|---|---|---|
| Hand-set (paper) | 4.62 ± 0.16 | 4.89 ± 0.23 | 7.85 ± 0.29 |
| Plain count | 5.69 ± 0.18 (+23.2%, p < 0.001) | 5.99 ± 0.18 (+22.7%, p < 0.001) | 8.90 ± 0.24 (+13.4%, p < 0.001) |
| Calibrated | 4.53 ± 0.20 (-2.0%, p 0.374) | 4.64 ± 0.15 (-4.9%, p 0.036) | 8.03 ± 0.32 (+2.2%, p 0.014) |

Change and p: paired against the hand-set weights on the same held-out seeds.
Signal safety audit over all 174 runs: 0 violations.
