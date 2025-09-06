import os, asyncio, time, csv
from typing import List, Dict, Any
from aiokafka import AIOKafkaConsumer
import numpy as np, redis.asyncio as redis
from prometheus_client import Counter, Histogram, start_http_server
from sqlalchemy import create_engine, text
from .features import OnlineFeatures
from .model import score_onnx, score_sklearn, make_onnx_session
from .config import BROKERS, TOPIC, GROUP_ID, METRICS_PORT, BATCH_SIZE, REDIS_URL, PG_DSN, ANOMALY_THRESHOLD

REQUESTS = Counter("events_processed_total", "Total events processed")
ANOMALIES = Counter("events_anomalies_total", "Total anomalies flagged")
LATENCY = Histogram("event_latency_seconds", "End-to-end latency seconds",
                    buckets=(.05,.1,.2,.3,.5,.75,1,1.5,2,3,5,10))

def parse_line(line: bytes):
    s = line.decode()
    id, ts, user_id, amount, country, device = s.strip().split(",")
    return {"id": id, "ts": float(ts), "user_id": int(user_id), "amount": float(amount), "country": country, "device": device}

class Consumer:
    def __init__(self, onnx_path="model.onnx"):
        self.batch_size = BATCH_SIZE
        self.features = OnlineFeatures()
        self.rdb = None
        self.pg = create_engine(PG_DSN, future=True)
        # prepare sink table
        with self.pg.begin() as conn:
            conn.execute(text("""
                CREATE SCHEMA IF NOT EXISTS fraud;
                CREATE TABLE IF NOT EXISTS fraud.anomalies(
                  id TEXT PRIMARY KEY,
                  ts DOUBLE PRECISION,
                  user_id BIGINT,
                  amount DOUBLE PRECISION,
                  country TEXT,
                  device TEXT,
                  score DOUBLE PRECISION
                );
            """))
        # ONNX session
        with open(onnx_path, "rb") as f:
            self.sess = make_onnx_session(f.read())

    async def run(self):
        start_http_server(METRICS_PORT)
        self.rdb = await redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=False)
        consumer = AIOKafkaConsumer(TOPIC, bootstrap_servers=BROKERS, group_id=GROUP_ID, enable_auto_commit=True)
        await consumer.start()
        try:
            batch = []
            async for msg in consumer:
                ev = parse_line(msg.value)
                batch.append(ev)
                if len(batch) >= self.batch_size:
                    await self._process_batch(batch); batch.clear()
        finally:
            await consumer.stop()

    async def _process_batch(self, batch: List[Dict[str, Any]]):
        rows = []
        now = time.time()
        X = []
        meta = []
        for ev in batch:
            feats = self.features.update_and_get(ev["user_id"], ev["amount"], ev["ts"])
            feats["amount"] = ev["amount"]
            X.append([feats["amount"], feats["user_avg_60s"], feats["user_std_60s"],
                      feats["user_count_60s"], feats["delta_from_last"], feats["z_amount"]])
            meta.append(ev)
        X = np.asarray(X, dtype=np.float32)
        labels, scores = score_onnx(self.sess, X)
        for ev, score in zip(meta, scores):
            latency = now - ev["ts"]
            LATENCY.observe(latency)
            REQUESTS.inc()
            if score < ANOMALY_THRESHOLD:
                ANOMALIES.inc()
                rows.append(ev | {"score": float(score)})
        if rows:
            # batch insert
            values = ",".join(
                ["(:id_{i}, :ts_{i}, :user_id_{i}, :amount_{i}, :country_{i}, :device_{i}, :score_{i})".format(i=i) for i in range(len(rows))]
            )
            params = {}
            for i, r in enumerate(rows):
                params.update({f"id_{i}": r["id"], f"ts_{i}": r["ts"], f"user_id_{i}": r["user_id"],
                               f"amount_{i}": r["amount"], f"country_{i}": r["country"], f"device_{i}": r["device"], f"score_{i}": r["score"]})
            stmt = text("INSERT INTO fraud.anomalies(id,ts,user_id,amount,country,device,score) VALUES " + values + " ON CONFLICT (id) DO NOTHING")
            with self.pg.begin() as conn:
                conn.execute(stmt, params)
