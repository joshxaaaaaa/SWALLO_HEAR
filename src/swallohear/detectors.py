"""M0 energy baseline and M1 Random Forest. M2 (CNN) is added later in models_cnn.py."""
from __future__ import annotations
import numpy as np
from scipy.signal import butter, sosfiltfilt
from scipy.ndimage import uniform_filter1d
from .features import frame_features, frame_energy_db
from .preprocess import frame_signal
from . import TARGET_FS

class EnergyDetector:
    """M0: smoothed 100-1000 Hz energy vs adaptive threshold (noise floor + k * MAD). Returns pseudo-probabilities."""
    name = "M0 energy"
    def __init__(self, k=3.0): self.k = k
    def predict_proba(self, x):
        sos = butter(4, [100, 1000], btype="band", fs=TARGET_FS, output="sos")
        e = frame_energy_db(frame_signal(sosfiltfilt(sos, x)))
        e = uniform_filter1d(e, 9)
        floor = np.percentile(e, 10); mad = np.median(np.abs(e - np.median(e))) * 1.4826 + 1e-6
        z = (e - floor) / mad
        return 1 / (1 + np.exp(-(z - self.k)))   # soft threshold centered at k

class RFDetector:
    """M1: Random Forest on frame features."""
    name = "M1 RandomForest"
    def __init__(self, n_estimators=100, seed=0):
        from sklearn.ensemble import RandomForestClassifier
        self.clf = RandomForestClassifier(n_estimators=n_estimators, class_weight="balanced_subsample",
                                          min_samples_leaf=50, n_jobs=-1, random_state=seed)
    def fit(self, X, y): self.clf.fit(X, y); return self
    def predict_proba(self, x): return self.clf.predict_proba(frame_features(x))[:, 1]
