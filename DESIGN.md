# DESIGN.md — Real‑Time Fraud Detection POC (2 pages)

## 1. Objective & Scope
Build a near‑real‑time fraud detection pipeline that ingests transactions, computes lightweight online features, scores with a compact model, and emits alerts within **p95 < 2s**. The POC demonstrates production‑style concerns (throughput, latency, backpressure, observability) on developer hardware with Docker‑based infra.

**Out of scope:** enterprise auth, PII handling beyond dev, complex stateful joins, human‑in‑the‑loop triage tooling.

## 2. SLOs & Capacity Plan
- **Latency SLO:** p95 end‑to‑end < 2s (ingest → features → model → sink)
- **Availability:** best‑effort (dev), at‑least‑once semantics with idempotent sink
- **Throughput target:** simulate **5M/day** ≈ 58 rps average; stress to **~800 rps peaks** for 5–10 min
- **Backpressure:** consumer micro‑batching; queue buffering in Kafka

**Partitioning:** topic `txns` with 8–16 partitions; one consumer per partition (scale horizontally).

## 3. Architecture
**Ingest:** Redpanda (Kafka) receives events via a Python producer streaming CSV/Parquet lines.  
**Consumer/Scorer:** Python async worker pulls micro‑batches, fetches per‑user rolling stats (Redis), scores with **ONNXRuntime** (IsolationForest), and writes anomalies to Postgres.  
**Storage:** Postgres table `fraud.anomalies` stores alerts; raw events can be landed to files (todo).  
**Observability:** Prometheus scrapes app metrics (`/metrics`), Grafana shows latency histograms, anomalies count, rps.

```
[ Producer ] -> [ Redpanda (Kafka) ] -> [ Python Consumer + Redis + ONNXRuntime ] -> [ Postgres (anomalies) ]
                                                     |-> Prometheus -> Grafana
```

## 4. Data Model & Features
Event schema (CSV): `id, ts, user_id, amount, country, device` (normalized floats/ints).  
**Online features (per user, rolling 60s):** count, avg, std, delta_from_last, z_amount.  
Aggregations are maintained in Redis for O(1) lookup/update per event.

## 5. Model
IsolationForest trained on synthetic “normal” distributions. Export path:
1) Train in sklearn  
2) Convert via `skl2onnx`  
3) Serve with `onnxruntime` for low‑latency inference.

**Thresholding:** treat ONNX `score` (decision_function) below `T` or label `-1` as anomalous. Threshold tuned to desired precision/recall trade‑off.

## 6. Latency Budget (target p95 < 2s)
- Kafka fetch + deserialize: 50–200 ms
- Redis online features: 20–150 ms
- ONNXRuntime score (batch 100–500): 5–100 ms
- Postgres write (async/batch): 50–300 ms
- Jitter/GC/network buffer: 400–800 ms

## 7. Failure Modes & Handling
- **Poison messages** → Dead‑letter queue/topic (todo) + alert.
- **Redis unavailability** → fallback to default features; log degraded mode.
- **Postgres outage** → buffer anomalies in memory (+retry/backoff); drop after watermark.
- **Consumer lag** → autoscale instances (not implemented in POC); investigate skew.

**Idempotency:** use event `id` as primary key in sink to avoid duplicate inserts.

## 8. Privacy & Security (POC)
No real PII; synthetic data only. In real systems, separate PII, encrypt at rest/in flight, audit access, and enforce data retention policies.

## 9. Rollout & Testing
- **Shadow mode:** run new model alongside current; compare alerts offline.
- **Load tests:** producer pushes controlled rps; verify p50/p95/p99 latency.
- **Canary deploy:** one partition / one consumer instance before fleet rollout.
- **Monitoring:** alert on p95 > 2s, consumer lag growth, error rate, Redis/DB saturation.

## 10. Cost & Impact Estimate
Savings ≈ baseline fraud losses × recall − (false‑positive handling + ops). Provide a range with sensitivity analysis in README or a separate note.
