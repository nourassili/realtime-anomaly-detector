import argparse, time
import numpy as np
from .model import train_iforest, to_onnx_bytes, make_onnx_session, score_sklearn, score_onnx

def synth_X(n=100_000, seed=42):
    rng = np.random.default_rng(seed)
    amount = np.abs(rng.normal(60, 25, size=n))
    user_avg = amount * rng.normal(1.0, 0.05, size=n)
    user_std = np.abs(rng.normal(15, 5, size=n))
    user_count = rng.integers(3, 40, size=n).astype(float)
    delta = rng.normal(0, 10, size=n)
    z = (amount - user_avg) / np.where(user_std < 1e-6, 1.0, user_std)
    X = np.column_stack([amount, user_avg, user_std, user_count, delta, z])
    return X

def bench(n_rows):
    X = synth_X(n_rows)
    model = train_iforest(X)
    onnx_bytes = to_onnx_bytes(model, X.shape[1])
    sess = make_onnx_session(onnx_bytes)

    # sklearn
    t0 = time.perf_counter(); _ = score_sklearn(model, X); t1 = time.perf_counter()
    # onnx
    t2 = time.perf_counter(); _ = score_onnx(sess, X.astype(np.float32)); t3 = time.perf_counter()

    sk_ms = (t1 - t0) * 1000.0
    onnx_ms = (t3 - t2) * 1000.0
    print(f"Rows: {n_rows:,}")
    print(f"Sklearn: {sk_ms:.1f} ms  |  {n_rows/(t1-t0):.0f} rows/s")
    print(f"ONNXRT : {onnx_ms:.1f} ms  |  {n_rows/(t3-t2):.0f} rows/s")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=500_000)
    args = ap.parse_args()
    bench(args.rows)
