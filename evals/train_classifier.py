r"""
Enhanced Architectural Pattern & Modernity Classifier (High Accuracy Edition).

Improvements:
1. Added High-Signal Architectural Features:
   - legacy_imports_count: javax.servlet, java.sql, ActionForm, HttpServlet, etc.
   - modern_imports_count: fastapi, pydantic, sqlalchemy, BaseModel, APIRouter, etc.
   - max_nesting_depth: detects deep legacy indentation vs clean modular architecture
   - log_loc: log-transformed LOC for normalized scale stability
2. Hyperparameter Optimization:
   - n_estimators=200
   - max_depth=10
   - min_samples_split=3
   - min_samples_leaf=2
3. Balanced Stratified 5-Fold Cross Validation.
"""

import os
import re
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

LEGACY_DIR = Path(r"C:\projects")
MODERN_DIR = Path(r"C:\Users\Admin\OneDrive\Desktop\MP\modernized_projects")
MODEL_SAVE_DIR = Path(__file__).resolve().parent.parent / "services" / "api" / "ml"

VALID_EXTENSIONS = {".java", ".py", ".jsp", ".sql", ".js"}
IGNORED_PATTERNS = {".git", "__pycache__", "node_modules", "target", ".pytest_cache", ".vscode"}

LEGACY_SIGNALS = re.compile(r"\b(javax\.servlet|java\.sql|HttpServlet|ActionForm|ActionForward|JspWriter|ResultSet|Statement|PreparedStatement|org\.apache\.struts)\b", re.IGNORECASE)
MODERN_SIGNALS = re.compile(r"\b(fastapi|pydantic|BaseModel|ConfigDict|APIRouter|Depends|AsyncSession|sqlalchemy\.orm|SQLModel)\b", re.IGNORECASE)


def extract_features_from_file(file_path: Path, label: int) -> dict:
    """Extracts high-signal structural & architectural code metrics from a source file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    lines = content.splitlines()
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith(("#", "//", "/*", "*"))]
    loc = len(code_lines)
    if loc == 0:
        return None

    # 1. Cyclomatic Complexity Heuristic
    branches = len(re.findall(r"\b(if|else if|elif|for|while|case|catch|except)\b", content))
    cyclomatic_complexity = max(1, branches)

    # 2. Maximum Nesting / Indentation Depth
    nesting_depths = [len(l) - len(l.lstrip()) for l in code_lines]
    max_nesting = max(nesting_depths) // 4 if nesting_depths else 0
    max_nesting = min(max_nesting, 10)

    # 3. SQL Keyword Density
    sql_keywords = len(re.findall(r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|CREATE TABLE|ALTER TABLE)\b", content, re.IGNORECASE))
    sql_density = sql_keywords / loc if loc > 0 else 0.0

    # 4. Class & Method counts
    classes = len(re.findall(r"\b(class|interface)\s+[A-Za-z0-9_]+", content))
    methods = len(re.findall(r"\b(def|public|private|protected)\s+[A-Za-z0-9_]+\s*\(", content))

    # 5. Comment ratio
    comment_lines = len([l for l in lines if l.strip().startswith(("#", "//", "/*", "*"))])
    comment_ratio = comment_lines / (loc + comment_lines) if (loc + comment_lines) > 0 else 0.0

    # 6. High-Signal Import / Token Signatures
    legacy_imports = len(LEGACY_SIGNALS.findall(content))
    modern_imports = len(MODERN_SIGNALS.findall(content))

    return {
        "file_name": file_path.name,
        "loc": loc,
        "log_loc": np.log1p(loc),
        "cyclomatic_complexity": cyclomatic_complexity,
        "max_nesting": max_nesting,
        "sql_density": round(sql_density, 4),
        "classes": classes,
        "methods": methods,
        "comment_ratio": round(comment_ratio, 4),
        "legacy_imports": legacy_imports,
        "modern_imports": modern_imports,
        "label": label  # 0: Legacy Monolith, 1: Legacy Data Access/SQL, 2: Modern Microservice
    }


def build_dataset() -> pd.DataFrame:
    records = []

    # 1. Process Legacy Files
    for p in LEGACY_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS:
            if any(ign in str(p) for ign in IGNORED_PATTERNS):
                continue
            is_dao = "dao" in p.name.lower() or p.suffix.lower() == ".sql" or "db" in p.name.lower()
            label = 1 if is_dao else 0
            feats = extract_features_from_file(p, label=label)
            if feats:
                records.append(feats)

    # 2. Process Modernized Files (Label: 2)
    for p in MODERN_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS:
            if any(ign in str(p) for ign in IGNORED_PATTERNS):
                continue
            feats = extract_features_from_file(p, label=2)
            if feats:
                records.append(feats)

    return pd.DataFrame(records)


def main():
    print("=" * 80)
    print("TRAINING HIGH-ACCURACY 5-FOLD RANDOM FOREST ARCHITECTURAL CLASSIFIER")
    print("=" * 80)

    df = build_dataset()
    print(f"Total dataset size: {len(df)} files")
    print(f"Distribution: Legacy Monoliths={sum(df['label']==0)}, Legacy DAOs={sum(df['label']==1)}, Modern Microservices={sum(df['label']==2)}\n")

    feature_cols = [
        "log_loc",
        "cyclomatic_complexity",
        "max_nesting",
        "sql_density",
        "classes",
        "methods",
        "comment_ratio",
        "legacy_imports",
        "modern_imports"
    ]
    X = df[feature_cols].values
    y = df["label"].values

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    fold_accuracies = []
    fold_precisions = []
    fold_recalls = []
    fold_f1s = []

    print(f"{'Fold':<8} | {'Accuracy (%)':<15} | {'Precision (%)':<15} | {'Recall (%)':<15} | {'F1-Score (%)':<15}")
    print("-" * 75)

    best_clf = None
    best_acc = 0.0

    for fold_num, (train_idx, test_idx) in enumerate(skf.split(X, y), 1):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        clf = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=3,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42 + fold_num
        )
        clf.fit(X_train, y_train)

        y_pred = clf.predict(X_test)

        acc = accuracy_score(y_test, y_pred) * 100
        prec = precision_score(y_test, y_pred, average="weighted", zero_division=0) * 100
        rec = recall_score(y_test, y_pred, average="weighted", zero_division=0) * 100
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0) * 100

        fold_accuracies.append(acc)
        fold_precisions.append(prec)
        fold_recalls.append(rec)
        fold_f1s.append(f1)

        print(f"Fold {fold_num:<3} | {acc:<15.2f} | {prec:<15.2f} | {rec:<15.2f} | {f1:<15.2f}")

        if acc > best_acc:
            best_acc = acc
            best_clf = clf

    print("-" * 75)
    mean_acc = np.mean(fold_accuracies)
    std_acc = np.std(fold_accuracies)
    mean_prec = np.mean(fold_precisions)
    mean_rec = np.mean(fold_recalls)
    mean_f1 = np.mean(fold_f1s)

    print(f"{'MEAN':<8} | {mean_acc:5.2f}% (+/-{std_acc:.2f}) | {mean_prec:5.2f}%         | {mean_rec:5.2f}%         | {mean_f1:5.2f}%\n")

    # Feature Importance Breakdown
    importances = best_clf.feature_importances_
    print("--- TOP FEATURE IMPORTANCE ---")
    feat_importances = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)
    for feat, imp in feat_importances:
        print(f"  - {feat:<25}: {imp * 100:5.2f}%")

    MODEL_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_clf, MODEL_SAVE_DIR / "architectural_classifier.joblib")
    df.to_csv(MODEL_SAVE_DIR / "code_metrics_dataset.csv", index=False)
    print(f"\nSaved optimized model to: {MODEL_SAVE_DIR / 'architectural_classifier.joblib'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
