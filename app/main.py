import asyncio, os
from .consumer import Consumer

async def main():
    # Expect an ONNX model at ./model.onnx; if missing, create one quickly.
    if not os.path.exists("model.onnx"):
        from .benchmark_onnx import synth_X
        from .model import train_iforest, to_onnx_bytes
        X = synth_X(100_000)
        model = train_iforest(X)
        with open("model.onnx","wb") as f:
            f.write(to_onnx_bytes(model, X.shape[1]))
    c = Consumer(onnx_path="model.onnx")
    await c.run()

if __name__ == "__main__":
    asyncio.run(main())
