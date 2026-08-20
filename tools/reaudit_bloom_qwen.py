"""One-off re-evaluation pass: run all 100 already-approved items from
entregavel_2_100_questoes_design_d_full.csv through qwen3.6-27b's
judge_agent() (blind-solve + Bloom-alignment check), WITHOUT any
generation -- reusing the pipeline's own judge_agent()/GeneratedItem/
build_judge_messages so this is the exact same check a real run would
apply, just replayed against already-existing item text. Read-only:
never touches entregavel_2_100_questoes_design_d_full.csv itself.
"""
import asyncio
import json
import random
import sys

import pandas as pd

sys.path.insert(0, "/home/CIN/vflc/meu_projeto_mestrado")
from WAPLA_AIG_Engine import GeneratedItem, judge_agent, SEED  # noqa: E402

JUDGE_MODEL = "vllm_local/qwen3.6-27b@8001"
CSV_PATH = "output/entregavel_2_100_questoes_design_d_full.csv"
OUT_PATH = "output/reaudit_bloom_qwen_pool100.jsonl"


def row_to_item(row: pd.Series) -> GeneratedItem:
    def s(col):
        v = row.get(col)
        return None if pd.isna(v) else str(v)

    return GeneratedItem(
        base_text=s("base_text"),
        stem=s("stem"),
        statement_i=s("statement_i"),
        statement_ii=s("statement_ii"),
        statement_iii=s("statement_iii"),
        statement_iv=s("statement_iv"),
        assertion_i=s("assertion_i"),
        assertion_ii=s("assertion_ii"),
        option_a=s("option_a"),
        option_b=s("option_b"),
        option_c=s("option_c"),
        option_d=s("option_d"),
        option_e=s("option_e"),
        correct_option=s("correct_option"),
    )


async def main():
    df = pd.read_csv(CSV_PATH)
    assert len(df) == 100, f"expected 100 rows, got {len(df)}"

    results = []
    with open(OUT_PATH, "w", encoding="utf-8") as out_f:
        for i, row in df.iterrows():
            qid = int(row["question_id"])
            target_letter = str(row["correct_option"]).strip().upper()
            target_level = str(row["taxonomy_level"])
            item = row_to_item(row)
            item_rng = random.Random(f"reaudit-{qid}-{SEED}")
            try:
                outcome = await judge_agent(
                    item, target_letter, target_level, JUDGE_MODEL,
                    item_rng=item_rng, n_reorderings=1,
                )
                rv = outcome.raw_verdict
                record = {
                    "question_id": qid,
                    "taxonomy_level": target_level,
                    "approved": outcome.approved,
                    "bloom_alignment_ok": rv.bloom_alignment_ok if rv else None,
                    "mutual_exclusivity_ok": rv.mutual_exclusivity_ok if rv else None,
                    "length_bias_ok": rv.length_bias_ok if rv else None,
                    "factual_soundness_ok": rv.factual_soundness_ok if rv else None,
                    "reasons": outcome.reasons,
                }
            except Exception as exc:  # noqa: BLE001
                record = {"question_id": qid, "taxonomy_level": target_level,
                          "error": str(exc)}
            results.append(record)
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            print(f"[{i+1}/100] qid={qid} bloom_ok={record.get('bloom_alignment_ok')} "
                  f"approved={record.get('approved')}", flush=True)

    n_bloom_fail = sum(1 for r in results if r.get("bloom_alignment_ok") is False)
    n_approved = sum(1 for r in results if r.get("approved") is True)
    n_errors = sum(1 for r in results if "error" in r)
    print("=" * 70)
    print(f"Total re-evaluated: {len(results)}")
    print(f"bloom_alignment_ok=False: {n_bloom_fail} ({n_bloom_fail/len(results)*100:.1f}%)")
    print(f"Would-still-approve (all checks incl. Bloom): {n_approved} ({n_approved/len(results)*100:.1f}%)")
    print(f"Errors: {n_errors}")


if __name__ == "__main__":
    asyncio.run(main())
