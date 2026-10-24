Ablation of the adaptive controller: 10 paired seeds x 1800 s per row; change and p are relative to the reference at the same demand.

| Variant | Demand | Mean delay (s) | Change | p | 95th-pct. delay (s) | Mean green (s) |
|---|---|---|---|---|---|---|
| Adaptive (reference) | medium | 4.60 ± 0.14 | — | — | 14.2 ± 0.6 | 9.5 ± 0.2 |
| Unweighted count (weights and multipliers = 1) | medium | 5.65 ± 0.16 | +22.7% | < 0.001 | 18.2 ± 0.5 | 14.1 ± 0.3 |
| No class weights (all classes = 1) | medium | 4.42 ± 0.14 | -3.9% | 0.065 | 13.2 ± 0.2 | 8.9 ± 0.1 |
| No queued/moving distinction (multipliers = 1) | medium | 6.22 ± 0.21 | +35.1% | < 0.001 | 21.2 ± 0.7 | 15.1 ± 0.3 |
| theta = 1.0 | medium | 4.66 ± 0.13 | +1.3% | 0.390 | 15.0 ± 0.8 | 10.0 ± 0.3 |
| theta = 1.5 | medium | 4.38 ± 0.13 | -4.9% | 0.005 | 13.2 ± 0.5 | 8.8 ± 0.2 |
| + discharge hold, 10 m zone | medium | 4.62 ± 0.16 | +0.4% | 0.816 | 14.2 ± 0.5 | 9.7 ± 0.2 |
| + discharge hold, 20 m zone | medium | 4.66 ± 0.14 | +1.3% | 0.440 | 14.5 ± 0.6 | 9.8 ± 0.2 |
| + discharge hold, 30 m zone | medium | 4.61 ± 0.12 | +0.2% | 0.924 | 14.9 ± 0.5 | 10.5 ± 0.2 |
| Preemption off | medium | 4.24 ± 0.09 | -7.8% | < 0.001 | 13.1 ± 0.1 | 9.2 ± 0.1 |
| Fixed 20 s (for reference) | medium | 7.20 ± 0.20 | +56.5% | < 0.001 | 23.5 ± 0.3 | 19.6 ± 0.4 |
| Adaptive (reference) | high | 4.76 ± 0.12 | — | — | 14.8 ± 1.0 | 9.5 ± 0.2 |
| Unweighted count (weights and multipliers = 1) | high | 6.03 ± 0.19 | +26.6% | < 0.001 | 19.5 ± 0.8 | 14.3 ± 0.3 |
| No class weights (all classes = 1) | high | 4.61 ± 0.15 | -3.2% | 0.037 | 14.0 ± 0.9 | 9.1 ± 0.2 |
| No queued/moving distinction (multipliers = 1) | high | 6.34 ± 0.15 | +33.0% | < 0.001 | 21.0 ± 0.6 | 15.0 ± 0.2 |
| theta = 1.0 | high | 4.75 ± 0.14 | -0.3% | 0.844 | 14.8 ± 0.6 | 9.8 ± 0.1 |
| theta = 1.5 | high | 4.57 ± 0.14 | -4.1% | 0.061 | 13.5 ± 0.3 | 8.9 ± 0.1 |
| + discharge hold, 10 m zone | high | 4.89 ± 0.23 | +2.5% | 0.172 | 15.3 ± 1.5 | 9.7 ± 0.2 |
| + discharge hold, 20 m zone | high | 4.87 ± 0.15 | +2.2% | 0.058 | 15.5 ± 1.2 | 10.0 ± 0.3 |
| + discharge hold, 30 m zone | high | 4.94 ± 0.19 | +3.6% | 0.088 | 16.4 ± 1.1 | 10.9 ± 0.3 |
| Preemption off | high | 4.22 ± 0.06 | -11.4% | < 0.001 | 12.9 ± 0.1 | 8.9 ± 0.1 |
| Fixed 20 s (for reference) | high | 7.36 ± 0.22 | +54.5% | < 0.001 | 23.6 ± 0.3 | 19.3 ± 0.6 |

Mean ± 95% confidence interval over seeds; p = paired t-test.
Signal safety audit over all 220 runs: 0 violations.
