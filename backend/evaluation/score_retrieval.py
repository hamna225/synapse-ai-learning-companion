"""Score source-location retrieval against the bundled course benchmark."""

import argparse
import json
from pathlib import Path

from rag.retriever import get_retriever


BASE_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--material-id",
        default="material_3d86acbfc9e4",
        help="Uploaded material ID whose Chroma collection should be evaluated.",
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", default="retrieval_results.json")
    args = parser.parse_args()

    benchmark = json.loads((BASE_DIR / "benchmark.json").read_text(encoding="utf-8"))
    retriever = get_retriever(args.material_id)
    retriever.search_kwargs["k"] = args.k

    results = []
    precisions = []
    recalls = []

    for case in benchmark["cases"]:
        if case["kind"] == "off_material":
            continue

        docs = retriever.invoke(case["question"])
        expected = {int(slide) for slide in case["expected_slides"]}
        retrieved = [doc.metadata.get("slide") for doc in docs]
        relevant = {int(slide) for slide in retrieved if slide is not None} & expected
        precision = len(relevant) / len(docs) if docs else 0.0
        recall = len(relevant) / len(expected) if expected else 0.0
        precisions.append(precision)
        recalls.append(recall)
        results.append({
            "id": case["id"],
            "kind": case["kind"],
            "expected_slides": sorted(expected),
            "retrieved_slides": retrieved,
            "source_precision_at_k": round(precision, 3),
            "source_recall_at_k": round(recall, 3),
        })

    report = {
        "material_id": args.material_id,
        "k": args.k,
        "evaluated_answerable_cases": len(results),
        "mean_source_precision_at_k": round(sum(precisions) / len(precisions), 3) if precisions else 0.0,
        "mean_source_recall_at_k": round(sum(recalls) / len(recalls), 3) if recalls else 0.0,
        "note": "Source-location retrieval proxy based on matching retrieved slide metadata to known relevant slides; not a full RAGAS score.",
        "cases": results,
    }

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = BASE_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
    print(f"Per-question results saved to {output_path}")


if __name__ == "__main__":
    main()
