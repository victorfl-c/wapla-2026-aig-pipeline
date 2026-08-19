"""Module 9 / constitution R41 -- cross-item diversity check.

Computes pairwise TF-IDF cosine similarity across the stems of a delivered
item batch, per Zhang et al. (2601.17717, TMLR) 's Self-CosSim metric
(spec.md Sec 7.2): a batch that is individually valid per item but
redundant across items still fails R41. This is a standalone, read-only
audit -- it does not gate acceptance or modify the deliverable CSV/audit
trail; it only reports.

Usage: python3 tools/diversity_check_r41.py <deliverable_csv> [threshold]
"""
import sys

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def diversity_report(csv_path: str, threshold: float = 0.85) -> None:
    df = pd.read_csv(csv_path)
    stems = df["stem"].fillna("").astype(str).tolist()
    qids = df["question_id"].tolist()
    qtypes = df["question_type"].tolist()

    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform(stems)
    sim = cosine_similarity(tfidf)

    n = len(stems)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((sim[i, j], qids[i], qids[j], qtypes[i], qtypes[j]))

    mean_sim = sum(p[0] for p in pairs) / len(pairs)
    max_sim = max(pairs, key=lambda p: p[0])
    flagged = sorted((p for p in pairs if p[0] >= threshold), key=lambda p: -p[0])

    print(f"Items: {n}")
    print(f"Pairs compared: {len(pairs)}")
    print(f"Mean pairwise cosine similarity (Self-CosSim): {mean_sim:.4f}")
    print(f"Max pairwise similarity: {max_sim[0]:.4f}  (question_id {max_sim[1]} [{max_sim[3]}] vs {max_sim[2]} [{max_sim[4]}])")
    print(f"Pairs at/above near-duplicate threshold ({threshold}): {len(flagged)}")
    for s, qi, qj, ti, tj in flagged:
        print(f"  {s:.4f}  question_id {qi} [{ti}]  <->  question_id {qj} [{tj}]")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "output/entregavel_2_100_questoes_design_d_full.csv"
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.85
    diversity_report(csv_path, threshold)
