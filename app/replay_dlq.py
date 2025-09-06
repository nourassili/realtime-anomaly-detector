import argparse, asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

async def replay(brokers, src, dst, rps):
    consumer = AIOKafkaConsumer(
        src, bootstrap_servers=brokers, group_id=None,
        enable_auto_commit=False, auto_offset_reset="earliest"
    )
    producer = AIOKafkaProducer(bootstrap_servers=brokers)
    await consumer.start(); await producer.start()
    try:
        interval = 1.0 / max(rps, 1)
        async for msg in consumer:
            await producer.send_and_wait(dst, msg.value)
            await asyncio.sleep(interval)
    finally:
        await consumer.stop(); await producer.stop()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brokers", default="localhost:19092")
    ap.add_argument("--src", default="txns_dlq")
    ap.add_argument("--dst", default="txns")
    ap.add_argument("--rps", type=int, default=200)
    args = ap.parse_args()
    asyncio.run(replay(args.brokers, args.src, args.dst, args.rps))

if __name__ == "__main__":
    main()
