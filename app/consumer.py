import os, asyncio, time
from typing import List, Dict, Any, Tuple
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import numpy as np, redis.asyncio as redis
from prometheus_client import Counter, Histogram, start_http_server
from sqlalchemy import create_engine, text
from .features import OnlineFeatures
from .model import score_onnx, make_onnx_session
from .config import (
    BROKERS, TOPIC, GROUP_ID, METRICS_PORT, BATCH_SIZE,
    REDIS_URL, PG_DSN, ANOMALY_THRESHOLD,  # existing
    DLQ_TOPIC,                              # new in config.py
)

# Metrics
REQUESTS = Counter("events_processed_total", "Total events read from Kafka")
ANOMALIES = Counter("events_anomalies_total", "Total anomalies flagged")
DLQED    = Counter("events_dlq_total", "Total events sent to DLQ")
LATENCY  = Histogram(
    "event_latency_seconds", "End-to-end latency seconds",
    buckets=(.05,.1,.2,.3,.5,.75,1,1.5,2,3,5,10)
)

def parse_line(line: bytes) -> Dict[str, Any]:
    s = line.decode()
    id, ts, user_id, amount, country, device = s.strip().split(",")
    return {
        "id": id, "ts": float(ts), "user_id": int(user_id),
        "amount": float(amount), "country": country, "device": device
    }

class Consumer:
    def __init__(self, onnx_path="model.onnx"):
        self.batch_size = BATCH_SIZE
        self.features = OnlineFeatures()
        self.rdb = None
        self.pg = create_engine(PG_DSN, future=True)
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
        with open(onnx_path, "rb") as f:
            self.sess = make_onnx_session(f.read())
        self.dlq = None  # AIOKafkaProducer (initialized in run)

    async def run(self):
        start_http_server(METRICS_PORT)
        self.rdb = await redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=False)
        consumer = AIOKafkaConsumer(
            TOPIC, bootstrap_servers=BROKERS, group_id=GROUP_ID, enable_auto_commit=True
        )
        self.dlq = AIOKafkaProducer(bootstrap_servers=BROKERS)
        await consumer.start()
        await self.dlq.start()
        try:
