import argparse, asyncio, csv, time
from aiokafka import AIOKafkaProducer

async def produce(file, topic, brokers, rps):
    prod = AIOKafkaProducer(bootstrap_servers=brokers)
    await prod.start()
    try:
        interval = 1.0 / max(rps,1)
        with open(file) as f:
            rd = csv.DictReader(f)
            batch = []
            last = time.perf_counter()
            for row in rd:
                msg = f"{row['id']},{row['ts']},{row['user_id']},{row['amount']},{row['country']},{row['device']}".encode()
                await prod.send_and_wait(topic, msg)
                # pace
                now = time.perf_counter()
                elapsed = now - last
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)
                last = time.perf_counter()
    finally:
        await prod.stop()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--topic", default="txns")
    ap.add_argument("--brokers", default="localhost:19092")
    ap.add_argument("--rps", type=int, default=400)
    args = ap.parse_args()
    asyncio.run(produce(args.file, args.topic, args.brokers, args.rps))

if __name__ == "__main__":
    main()
