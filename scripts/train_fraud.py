"""Train a REAL fraud classifier on the carclaims auto-insurance dataset.

Real data (Angoss/Oracle, 15,420 records, 923 fraud). No synthetic oversampling —
class imbalance is handled with XGBoost's scale_pos_weight (no SMOTE).

Usage:
    backend/.venv/bin/python scripts/train_fraud.py
Outputs: models/fraud_xgb.joblib, models/fraud_metrics.json (+ console report).
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "fraud" / "carclaims.csv"
OUT = ROOT / "models"
OUT.mkdir(exist_ok=True)
TARGET = "FraudFound"
DROP = ["PolicyNumber"]  # row identifier, not predictive


def main() -> None:
    df = pd.read_csv(CSV)
    print(f"Loaded {len(df):,} real records from {CSV.name}")

    y = (df[TARGET].astype(str).str.strip().str.lower() == "yes").astype(int)
    X = df.drop(columns=[TARGET, *[c for c in DROP if c in df.columns]])

    obj_cols = X.select_dtypes(include="object").columns.tolist()
    X = pd.get_dummies(X, columns=obj_cols, drop_first=False)
    feature_names = X.columns.tolist()
    print(f"Features after encoding: {len(feature_names)}  |  fraud rate: {y.mean():.2%}")

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    spw = (y_tr == 0).sum() / max((y_tr == 1).sum(), 1)
    print(f"Train {len(X_tr):,} / Test {len(X_te):,}  |  scale_pos_weight={spw:.1f}")

    model = XGBClassifier(
        n_estimators=500, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="aucpr",
        scale_pos_weight=spw, n_jobs=-1, random_state=42,
    )
    model.fit(X_tr, y_tr)

    proba = model.predict_proba(X_te)[:, 1]
    roc = roc_auc_score(y_te, proba)
    pr_auc = average_precision_score(y_te, proba)

    # Default 0.5 threshold + a recall-oriented threshold (best F1).
    prec, rec, thr = precision_recall_curve(y_te, proba)
    f1s = 2 * prec * rec / (prec + rec + 1e-9)
    best_i = int(np.nanargmax(f1s))
    best_thr = float(thr[min(best_i, len(thr) - 1)])

    pred_05 = (proba >= 0.5).astype(int)
    pred_best = (proba >= best_thr).astype(int)
    cm = confusion_matrix(y_te, pred_best)

    print("\n================ REAL FRAUD MODEL — TEST METRICS ================")
    print(f"ROC-AUC:        {roc:.3f}")
    print(f"PR-AUC (avg precision): {pr_auc:.3f}")
    print(f"\n--- threshold 0.50 ---\n{classification_report(y_te, pred_05, digits=3)}")
    print(f"--- best-F1 threshold {best_thr:.3f} (F1={f1_score(y_te, pred_best):.3f}) ---")
    print(classification_report(y_te, pred_best, digits=3))
    print(f"Confusion matrix @best-F1 [ [TN FP] [FN TP] ]:\n{cm.tolist()}")

    # SHAP — explainability (top drivers of fraud risk)
    print("\n================ SHAP — TOP FRAUD DRIVERS ================")
    sample = X_te.sample(min(1000, len(X_te)), random_state=0)
    expl = shap.TreeExplainer(model)
    sv = expl.shap_values(sample)
    mean_abs = np.abs(sv).mean(axis=0)
    top = sorted(zip(feature_names, mean_abs), key=lambda x: x[1], reverse=True)[:15]
    for name, val in top:
        print(f"  {val:.4f}  {name}")

    joblib.dump({"model": model, "features": feature_names}, OUT / "fraud_xgb.joblib")
    metrics = {
        "dataset": "carclaims (real auto-insurance fraud)",
        "rows": len(df), "fraud_rate": float(y.mean()),
        "roc_auc": float(roc), "pr_auc": float(pr_auc),
        "best_f1_threshold": best_thr, "best_f1": float(f1_score(y_te, pred_best)),
        "confusion_matrix_best_f1": cm.tolist(),
        "top_features": [{"feature": n, "mean_abs_shap": float(v)} for n, v in top],
    }
    (OUT / "fraud_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nSaved model → {OUT/'fraud_xgb.joblib'}")
    print(f"Saved metrics → {OUT/'fraud_metrics.json'}")


if __name__ == "__main__":
    main()
