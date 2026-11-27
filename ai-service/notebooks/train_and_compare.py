"""Script pelatihan & perbandingan minimal 2 model NLP kustom untuk klasifikasi intent restock.
Dijalankan oleh Haryo Wicaksono (Next-Gen AI Engineer) pada branch feat/ai-restock-fastapi.
"""

import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "restock_intent_dataset.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def main():
    df = pd.read_csv(DATA_PATH)
    X = df["text"].astype(str)
    y = df["intent"].astype(str)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    candidates = {
        "TF-IDF + LinearSVC": Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
                ("clf", LinearSVC(random_state=42)),
            ]
        ),
        "TF-IDF + LogisticRegression": Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
                ("clf", LogisticRegression(max_iter=1000, random_state=42)),
            ]
        ),
        "TF-IDF + MultinomialNB": Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
                ("clf", MultinomialNB()),
            ]
        ),
    }

    results = []
    best_name = None
    best_pipeline = None
    best_f1 = -1.0

    print("=== Perbandingan Model Klasifikasi Intent Restock ===")
    for name, pipeline in candidates.items():
        pipeline.fit(X_train, y_train)
        preds = pipeline.predict(X_test)
        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, pos_label="restock_inventaris", zero_division=0)
        rec = recall_score(y_test, preds, pos_label="restock_inventaris", zero_division=0)
        f1 = f1_score(y_test, preds, pos_label="restock_inventaris", zero_division=0)

        results.append(
            {
                "model": name,
                "accuracy": round(float(acc), 4),
                "precision": round(float(prec), 4),
                "recall": round(float(rec), 4),
                "f1_score": round(float(f1), 4),
            }
        )
        print(f"- {name}: Acc={acc:.4f} | Prec={prec:.4f} | Rec={rec:.4f} | F1={f1:.4f}")

        if f1 > best_f1:
            best_f1 = f1
            best_name = name
            best_pipeline = pipeline

    # Latih ulang model terbaik pada seluruh dataset sebelum disimpan untuk serving
    best_pipeline.fit(X, y)
    model_path = MODEL_DIR / "intent_classifier.pkl"
    joblib.dump(best_pipeline, model_path)

    meta_path = MODEL_DIR / "model_comparison.json"
    meta_path.write_text(
        json.dumps(
            {"best_model": best_name, "dataset_size": len(df), "comparison": results},
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nModel terbaik: {best_name} (F1={best_f1:.4f})")
    print(f"Disimpan ke: {model_path}")
    print("\nClassification report pada test split (model terbaik):")
    best_test_pipeline = candidates[best_name]
    best_test_pipeline.fit(X_train, y_train)
    print(classification_report(y_test, best_test_pipeline.predict(X_test)))


if __name__ == "__main__":
    main()
