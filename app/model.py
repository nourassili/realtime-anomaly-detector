import numpy as np
from sklearn.ensemble import IsolationForest
from skl2onnx import to_onnx
from skl2onnx.common.data_types import FloatTensorType
import onnxruntime as ort

FEATURES = ["amount","user_avg_60s","user_std_60s","user_count_60s","delta_from_last","z_amount"]

def train_iforest(X: np.ndarray, contamination: float = 0.01, random_state: int = 42):
    clf = IsolationForest(n_estimators=100, contamination=contamination, random_state=random_state)
    clf.fit(X)
    return clf

def to_onnx_bytes(model, n_features: int):
    return to_onnx(model, initial_types=[('float_input', FloatTensorType([None, n_features]))]).SerializeToString()

def make_onnx_session(onnx_bytes: bytes):
    return ort.InferenceSession(onnx_bytes, providers=['CPUExecutionProvider'])

def score_sklearn(model, X: np.ndarray):
    # IsolationForest decision_function: higher = less anomalous; prediction: +1 (inlier), -1 (outlier)
    preds = model.predict(X)
    scores = model.decision_function(X)
    return preds, scores

def score_onnx(sess, X: np.ndarray):
    # ONNX model exported from IsolationForest returns label and score (names vary). Use output names dynamically.
    in_name = sess.get_inputs()[0].name
    outs = sess.get_outputs()
    out_names = [o.name for o in outs]
    result = sess.run(out_names, {in_name: X.astype(np.float32)})
    # Try to pick label/score heuristically
    label = None; score = None
    for name, arr in zip(out_names, result):
        if arr.ndim == 1 or arr.shape[1] == 1:
            # candidate for label or score
            if label is None:
                label = arr
            else:
                score = arr
    if score is None:
        score = label
    if label is None:
        label = (score < 0).astype(np.int32)  # fallback heuristic
    return label.squeeze(), score.squeeze()
