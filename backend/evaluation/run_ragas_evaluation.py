"""Run a small RAGAS evaluation against the app's current tutor route."""

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(PROJECT_DIR / ".env")

DEFAULT_CASE_IDS = [
    "ml01", "ml03", "ml06", "ml13", "cite03", "cite05",
    "chart14", "chart18", "off01", "off02", "off03", "off04", "off05",
]
FLAG_PHRASES = (
    "not covered",
    "does not cover",
    "doesn't cover",
    "not explained in the material",
    "not explained in enough detail",
    "outside the uploaded material",
    "general explanation (outside",
)


def retrieve_like_tutor(retriever, question):
    slide = re.search(r"\bslide\s*#?\s*(\d+)\b", question, re.IGNORECASE)
    page = re.search(r"\bpage\s*#?\s*(\d+)\b", question, re.IGNORECASE)
    if slide:
        docs = retriever.vectorstore.similarity_search(
            question, k=5, filter={"slide": int(slide.group(1))}
        )
    elif page:
        docs = retriever.vectorstore.similarity_search(
            question, k=5, filter={"page": int(page.group(1))}
        )
    else:
        docs = retriever.invoke(question)
    # Match the app route, which supplies the retrieved top-five passages.
    return docs[:5]


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--material-id", default="material_58e6a8a98719")
    parser.add_argument("--case-ids", nargs="*", default=DEFAULT_CASE_IDS)
    parser.add_argument("--output", default="ragas_results.json")
    args = parser.parse_args()

    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY is missing from the project .env file.")

    # Import after loading the project .env so the real tutor uses its key.
    from openai import AsyncOpenAI
    from ragas.embeddings import HuggingFaceEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )
    from main import AskRequest, ask_question, get_tutor

    benchmark = json.loads((BASE_DIR / "benchmark.json").read_text(encoding="utf-8"))
    cases_by_id = {case["id"]: case for case in benchmark["cases"]}
    missing_ids = [case_id for case_id in args.case_ids if case_id not in cases_by_id]
    if missing_ids:
        raise SystemExit(f"Unknown benchmark case IDs: {', '.join(missing_ids)}")

    tutor_llm, retriever = get_tutor(args.material_id)
    eval_llm = llm_factory(
        os.getenv("GROQ_EVAL_MODEL", "openai/gpt-oss-20b"),
        provider="openai",
        client=AsyncOpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        ),
        temperature=0,
        max_tokens=1600,
    )
    eval_embeddings = HuggingFaceEmbeddings(
        model="sentence-transformers/all-MiniLM-L6-v2"
    )
    metrics = {
        "faithfulness": Faithfulness(llm=eval_llm),
        "answer_relevancy": AnswerRelevancy(
            llm=eval_llm,
            embeddings=eval_embeddings,
            strictness=1,
        ),
        "context_precision": ContextPrecision(llm=eval_llm),
        "context_recall": ContextRecall(llm=eval_llm),
    }

    metric_values = {name: [] for name in metrics}
    cases = []
    answerable_total = 0
    flagged_off_material = 0
    citation_location_hits = 0

    for case_id in args.case_ids:
        case = cases_by_id[case_id]
        print(f"Evaluating {case_id}: {case['question']}", flush=True)
        docs = retrieve_like_tutor(retriever, case["question"])
        response = ask_question(AskRequest(
            material_id=args.material_id,
            question=case["question"],
        ))
        answer = str(response.get("answer", ""))
        retrieved_contexts = [doc.page_content for doc in docs]
        expected_slides = {int(value) for value in case.get("expected_slides", [])}
        citation_numbers = {
            int(value) for value in re.findall(r"(?:\[|【)(\d+)(?:\]|】)", answer)
        }
        cited_slides = {
            int(doc.metadata["slide"])
            for number, doc in enumerate(docs, 1)
            if number in citation_numbers and doc.metadata.get("slide") is not None
        }

        result = {
            "id": case_id,
            "kind": case["kind"],
            "question": case["question"],
            "answer": answer,
            "retrieved_locations": [
                doc.metadata.get("slide", doc.metadata.get("page"))
                for doc in docs
            ],
            "expected_locations": sorted(expected_slides),
            "citation_location_hit": bool(expected_slides & cited_slides),
        }

        if case["kind"] == "off_material":
            flagged = any(phrase in answer.casefold() for phrase in FLAG_PHRASES)
            result["unsupported_query_flagged"] = flagged
            flagged_off_material += int(flagged)
        else:
            answerable_total += 1
            citation_location_hits += int(result["citation_location_hit"])
            reference = "; ".join(case.get("expected_facts", []))
            metric_inputs = {
                "user_input": case["question"],
                "response": answer,
                "retrieved_contexts": retrieved_contexts,
                "reference": reference,
            }
            result["metrics"] = {}
            for metric_name, metric in metrics.items():
                if metric_name == "faithfulness":
                    inputs = {key: metric_inputs[key] for key in (
                        "user_input", "response", "retrieved_contexts"
                    )}
                elif metric_name == "answer_relevancy":
                    inputs = {key: metric_inputs[key] for key in (
                        "user_input", "response"
                    )}
                else:
                    inputs = {key: metric_inputs[key] for key in (
                        "user_input", "retrieved_contexts", "reference"
                    )}
                score_result = await metric.ascore(**inputs)
                score = float(score_result.value)
                result["metrics"][metric_name] = score
                metric_values[metric_name].append(score)

        cases.append(result)

    report = {
        "framework": "RAGAS",
        "ragas_version": __import__("ragas").__version__,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "material_id": args.material_id,
        "evaluator_model": os.getenv("GROQ_EVAL_MODEL", "openai/gpt-oss-20b"),
        "scored_answerable_cases": answerable_total,
        "metrics_mean": {
            name: round(sum(values) / len(values), 4) if values else None
            for name, values in metric_values.items()
        },
        "citation_location_hit_rate": (
            round(citation_location_hits / answerable_total, 4)
            if answerable_total else None
        ),
        "off_material_flag_rate": (
            round(flagged_off_material / (len(args.case_ids) - answerable_total), 4)
            if len(args.case_ids) > answerable_total else None
        ),
        "off_material_check": "Deterministic phrase check for an explicit outside-material or not-covered flag; not a RAGAS metric.",
        "cases": cases,
    }
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = BASE_DIR / output_path
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
    print(f"Per-case results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
