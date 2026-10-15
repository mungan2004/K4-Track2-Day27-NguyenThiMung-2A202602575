# Reflection (≤1 page)

### Which fault types were hardest to catch, and why?

1. **Subtle Volume & Distribution Shifts in `data_batch`:**
   - Obvious faults (such as volume spikes >800 rows, null spikes >3%, and mean shifts >110) deviate clearly from baseline expectations.
   - However, the subtle-magnitude faults in the private phase (such as `volume_drop` with 469–474 rows, or subtle `distribution_shift` with mean amounts around 85–86) fall strictly within the clean stream's normal variance (clean row counts naturally span 435 to 561, and clean means span 77 to 88).
   - Because the scoring function penalizes false alarms heavily ($-0.3 \times \text{FPR}$ vs $+0.5 \times \text{TPR}$), loosening thresholds to capture these subtle shifts introduces false positives on clean batches, degrading overall score.

2. **Subtle Runtime Anomalies in `lineage_run`:**
   - Subtle runtime anomalies in the private stream ran between 4,480ms and 4,740ms. Clean runs naturally exhibited durations up to 4,805ms.
   - Without historical moving windows per job, duration alone cannot distinguish a subtle performance regression from ordinary network and query latency variance. In contrast, structural lineage faults (`missing_upstream` and `orphan_output`) were completely deterministic and caught with 100% precision.

3. **Subtle Corpus Staleness and Embedding Drift in `embedding_batch`:**
   - In private evaluations, subtle document age increases (31–37 days) and centroid shifts (~0.028–0.031) remained within the published baseline thresholds (49.8 days and 0.0435 shift). Without a clean-baseline reference point per corpus, static thresholds must be conservative to prevent false alarms.

---

### What would you change about your cost/coverage tradeoff, if you had another pass?

1. **Leverage `ctx.state` for Stateful Rolling Windows:**
   - While `ctx.baseline` provides global bounds, tracking moving averages and running standard deviations across consecutive batches per entity using Welford's algorithm would uncover subtle drift relative to recent history.
   - Sequential anomaly detection (e.g., CUSUM or EWMA) would detect persistent subtle shifts across multiple batches without firing false alarms on isolated variations.

2. **Multivariate Composite Anomaly Scoring:**
   - Instead of checking each metric in isolation, computing a Mahalanobis distance or composite score across correlated metrics (e.g., row count, staleness, null rate) would catch correlated low-magnitude deviations that individually pass univariate tests.

3. **Dynamic Budget Management for Constrained Streams:**
   - On the private phase with 320 credits, single-pass inspection cost exactly 300 credits ($0.0$ overage), maximizing TPR safely.
   - For streams with stricter budgets (such as public phase at 220 credits vs 240 single-pass cost), we could adaptively throttle high-cost checks ($2.0$ credits for feature drift and embedding drift) on alternating batches or based on upstream batch stability, eliminating cost overage penalties entirely.
