# Real‑Time Fraud Detection POC (Kafka/Redpanda + Python + Redis + Postgres)

**Goal:** Demonstrate a near‑real‑time fraud pipeline that handles **millions of events/day**, achieves **p95 < 2s** end‑to‑end, and ships with production‑style observability, Dockerized infra, and ONNX model serving.

---

## Stack
- **Ingest/Queue:** Redpanda (Kafka‑compatible)
- **Stream Producer:** Python CLI to stream synthetic data into Kafka
- **Scoring Consumer:** Python (async) with **micro‑batching**, online features (Redis), and **ONNX Runtime** inference (Isolation Forest exported via `skl2onnx`)
- **Storage:** Postgres (anomaly sink)
- **Cache:** Redis (per‑user rolling features)
- **Observability:** Prometheus (metrics), Grafana (pre‑baked dashboard)
- **Docker:** `docker-compose` with all services

---

## Quick Start

### 1) Infra
```bash
docker-compose up -d
# Wait ~15–30s for Redpanda, Postgres, Redis, Prometheus, Grafana, App
```

Grafana: http://localhost:3000  (user: `admin`, pass: `admin`)  
Prometheus: http://localhost:9090  
App metrics: http://localhost:9000/metrics

### 2) Generate data & produce to Kafka
```bash
# (Optional) Create a Python venv locally if you want to run tools outside Docker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Generate a synthetic CSV (default 1e6 rows; see --rows for more, up to 5e6)
python app/generate_data.py --rows 1000000 --out data_1m.csv

# Stream the CSV into Redpanda at ~400 rps (adjust --rps)
python app/producer.py --file data_1m.csv --topic txns --rps 400
```

### 3) Run the consumer/scorer (auto‑started in Docker)
The `app` service consumes from `txns`, does online feature lookups, scores with **ONNXRuntime**, and writes anomalies to Postgres (`fraud.anomalies`).  
Metrics (p50/p95/p99 latency, rps, anomalies) are exported at `/metrics` and auto‑scraped by Prometheus; Grafana shows them.

---

## Benchmarks & ONNX
Export your IsolationForest to **ONNX** and compare sklearn vs onnxruntime:
```bash
python app/benchmark_onnx.py --rows 500000
```
Outputs a small table with per‑record latency and throughput for both backends.

---

## Design Doc
See [`DESIGN.md`](DESIGN.md) for a 2‑page overview (SLOs, capacity plan, failure modes, rollout).

---

## Notes
- Redpanda is Kafka‑compatible and auto‑creates topics on first produce.
- Default credentials (dev only): Postgres `postgres:postgres` on `fraud` DB.  
- Grafana is pre‑provisioned with a Prometheus datasource and a dashboard for latency/rps/anomalies.
