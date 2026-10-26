"""
Kaithi Vision Recognition Evaluation Harness
Provides standard Character Error Rate (CER), Word Error Rate (WER),
glyph classification accuracy, and confidence calibration metrics.
"""

from typing import List, Dict, Any, Tuple, Optional
import time

def levenshtein_distance(seq1: List[Any], seq2: List[Any]) -> Tuple[int, int, int, int]:
    """
    Computes Levenshtein distance with operation counts.
    Returns: (total_distance, substitutions, deletions, insertions)
    """
    m, n = len(seq1), len(seq2)
    # dp[i][j] stores (cost, subs, dels, ins)
    dp = [[(0, 0, 0, 0) for _ in range(n + 1)] for _ in range(m + 1)]

    for i in range(1, m + 1):
        dp[i][0] = (i, 0, i, 0)  # i deletions
    for j in range(1, n + 1):
        dp[0][j] = (j, 0, 0, j)  # j insertions

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                # Substitution
                sub_cost = dp[i - 1][j - 1][0] + 1
                sub_tuple = (sub_cost, dp[i - 1][j - 1][1] + 1, dp[i - 1][j - 1][2], dp[i - 1][j - 1][3])

                # Deletion
                del_cost = dp[i - 1][j][0] + 1
                del_tuple = (del_cost, dp[i - 1][j][1], dp[i - 1][j][2] + 1, dp[i - 1][j][3])

                # Insertion
                ins_cost = dp[i][j - 1][0] + 1
                ins_tuple = (ins_cost, dp[i][j - 1][1], dp[i][j - 1][2], dp[i][j - 1][3] + 1)

                best = min([sub_tuple, del_tuple, ins_tuple], key=lambda x: x[0])
                dp[i][j] = best

    return dp[m][n]


class KaithiEvaluator:
    """
    Harness for computing Character Error Rate (CER) and Word Error Rate (WER)
    on historical script transcriptions.
    """

    @classmethod
    def compute_cer(cls, reference: str, hypothesis: str) -> Dict[str, Any]:
        """
        Computes CER = (S + D + I) / N
        where N is the number of characters in the reference.
        """
        ref_chars = list(reference)
        hyp_chars = list(hypothesis)
        n = len(ref_chars)

        if n == 0:
            if len(hyp_chars) == 0:
                return {"cer": 0.0, "substitutions": 0, "deletions": 0, "insertions": 0, "ref_length": 0}
            return {"cer": 1.0, "substitutions": 0, "deletions": 0, "insertions": len(hyp_chars), "ref_length": 0}

        dist, s, d, i = levenshtein_distance(ref_chars, hyp_chars)
        cer = round(dist / n, 4)

        return {
            "cer": cer,
            "accuracy": round(max(0.0, 1.0 - cer), 4),
            "distance": dist,
            "substitutions": s,
            "deletions": d,
            "insertions": i,
            "ref_length": n,
            "hyp_length": len(hyp_chars)
        }

    @classmethod
    def compute_wer(cls, reference: str, hypothesis: str) -> Dict[str, Any]:
        """
        Computes WER = (S + D + I) / N_words
        """
        ref_words = reference.strip().split()
        hyp_words = hypothesis.strip().split()
        n = len(ref_words)

        if n == 0:
            if len(hyp_words) == 0:
                return {"wer": 0.0, "substitutions": 0, "deletions": 0, "insertions": 0, "ref_words": 0}
            return {"wer": 1.0, "substitutions": 0, "deletions": 0, "insertions": len(hyp_words), "ref_words": 0}

        dist, s, d, i = levenshtein_distance(ref_words, hyp_words)
        wer = round(dist / n, 4)

        return {
            "wer": wer,
            "word_accuracy": round(max(0.0, 1.0 - wer), 4),
            "distance": dist,
            "substitutions": s,
            "deletions": d,
            "insertions": i,
            "ref_words": n,
            "hyp_words": len(hyp_words)
        }

    @classmethod
    def evaluate_benchmark_suite(
        cls,
        test_samples: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Evaluates a suite of reference-hypothesis pairs and aggregates metrics.
        """
        total_ref_chars = 0
        total_char_dist = 0
        total_ref_words = 0
        total_word_dist = 0
        sample_results = []

        for sample in test_samples:
            ref = sample["reference"]
            hyp = sample["hypothesis"]
            cer_res = cls.compute_cer(ref, hyp)
            wer_res = cls.compute_wer(ref, hyp)

            total_ref_chars += cer_res["ref_length"]
            total_char_dist += cer_res["distance"]
            total_ref_words += wer_res["ref_words"]
            total_word_dist += wer_res["distance"]

            sample_results.append({
                "sample_id": sample.get("id", "sample"),
                "cer": cer_res["cer"],
                "wer": wer_res["wer"],
                "details": {
                    "cer": cer_res,
                    "wer": wer_res
                }
            })

        overall_cer = round(total_char_dist / max(total_ref_chars, 1), 4)
        overall_wer = round(total_word_dist / max(total_ref_words, 1), 4)

        return {
            "total_samples": len(test_samples),
            "overall_cer": overall_cer,
            "overall_wer": overall_wer,
            "overall_char_accuracy": round(max(0.0, 1.0 - overall_cer), 4),
            "overall_word_accuracy": round(max(0.0, 1.0 - overall_wer), 4),
            "total_ref_chars": total_ref_chars,
            "total_ref_words": total_ref_words,
            "samples": sample_results
        }
