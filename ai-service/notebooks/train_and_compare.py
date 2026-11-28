"""Script pelatihan & perbandingan model NLP kustom untuk klasifikasi intent restock.
Membandingkan konfigurasi baseline vs tuned menggunakan Stratified 75/25 split dan 5-fold CV.
"""

import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "restock_intent_dataset.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def main():
    df = pd.read_csv(DATA_PATH)
    X = df["text"].astype(str)
    y = df["intent"].astype(str)

    class_counts = y.value_counts().to_dict()
    print("=== Distribusi Kelas Dataset ===")
    for label, count in class_counts.items():
        print(f"- {label}: {count} sampel")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    candidates = {
        "TF-IDF + LinearSVC (Baseline)": Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
                ("clf", LinearSVC(C=1.0, random_state=42)),
            ]
        ),
        "TF-IDF (Word+Char Sublinear) + LinearSVC (Tuned)": Pipeline(
            [
                (
                    "features",
                    FeatureUnion(
                        [
                            (
                                "word",
                                TfidfVectorizer(
                                    ngram_range=(1, 2),
                                    lowercase=True,
                                    sublinear_tf=True,
                                    token_pattern=r"(?u)\b\w+\b|\?",
                                ),
                            ),
                            (
                                "char",
                                TfidfVectorizer(
                                    analyzer="char_wb",
                                    ngram_range=(3, 5),
                                    lowercase=True,
                                    sublinear_tf=True,
                                ),
                            ),
                        ]
                    ),
                ),
                ("clf", LinearSVC(C=1.0, random_state=42)),
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
                ("clf", MultinomialNB(alpha=0.5)),
            ]
        ),
    }

    results = []
    best_name = None
    best_pipeline = None
    best_score = (-1.0, -1.0)

    print("\n=== Perbandingan Model Klasifikasi Intent Restock ===")
    for name, pipeline in candidates.items():
        cv_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="f1_macro")
        cv_f1_mean = float(cv_scores.mean())

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
                "cv_f1_macro": round(cv_f1_mean, 4),
            }
        )
        print(
            f"- {name}: Acc={acc:.4f} | Prec={prec:.4f} | Rec={rec:.4f} | "
            f"F1={f1:.4f} | CV-5 F1={cv_f1_mean:.4f}"
        )

        score_tuple = (round(float(f1), 6), round(cv_f1_mean, 6))
        if score_tuple > best_score:
            best_score = score_tuple
            best_name = name
            best_pipeline = pipeline

    # Latih ulang model terbaik pada seluruh dataset sebelum disimpan untuk serving
    best_pipeline.fit(X, y)
    model_path = MODEL_DIR / "intent_classifier.pkl"
    joblib.dump(best_pipeline, model_path)

    meta_path = MODEL_DIR / "model_comparison.json"
    meta_path.write_text(
        json.dumps(
            {
                "best_model": best_name,
                "dataset_size": int(len(df)),
                "train_size": int(len(X_train)),
                "test_size": int(len(X_test)),
                "class_distribution": {str(k): int(v) for k, v in class_counts.items()},
                "comparison": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nModel terbaik: {best_name} (Test F1={best_score[0]:.4f}, CV-5 F1={best_score[1]:.4f})")
    print(f"Disimpan ke: {model_path}")
    print("\nClassification report pada test split (model terbaik):")
    best_test_pipeline = candidates[best_name]
    best_test_pipeline.fit(X_train, y_train)
    print(classification_report(y_test, best_test_pipeline.predict(X_test)))


if __name__ == "__main__":
    main()
