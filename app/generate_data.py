import argparse, time, uuid, random, csv
from math import floor
COUNTRIES = ["US","GB","CA","MX","DE","FR","TR","AR","EG"]
DEVICES = ["ios","android","web"]

def synth_rows(n, anomaly_rate=0.005, seed=42):
    rnd = random.Random(seed)
    ts = time.time()
    for i in range(n):
        uid = rnd.randint(1, 1000000)
        if rnd.random() < anomaly_rate:
            amount = abs(rnd.gauss(5000, 2000))  # outlier
        else:
            amount = abs(rnd.gauss(60, 25))
        yield [str(uuid.uuid4()), f"{ts:.6f}", uid, round(amount,2), rnd.choice(COUNTRIES), rnd.choice(DEVICES)]
        # advance time slightly
        ts += rnd.random() * 0.01

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_000_000)
    ap.add_argument("--out", type=str, default="data.csv")
    ap.add_argument("--anomaly-rate", type=float, default=0.005)
    args = ap.parse_args()
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id","ts","user_id","amount","country","device"])
        for row in synth_rows(args.rows, args.anomaly_rate):
            w.writerow(row)
    print(f"Wrote {args.rows:,} rows to {args.out}")

if __name__ == "__main__":
    main()
