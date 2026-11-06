# Mini RAG evaluation

This benchmark uses the uploaded `Basics_of_Machine_Learning.pptx` deck. It has 15 answerable questions, 5 citation-focused questions, and 5 questions outside the deck. The expected facts and slide references were checked against the deck's extracted slide text.

## Run retrieval scoring

From the `backend` folder, with the virtual environment active:

```powershell
python -m evaluation.score_retrieval --material-id material_3d86acbfc9e4
```

The script reports mean source precision@5 and source recall@5 by checking whether the retrieved slides match each question's expected slide. These are a small source-location retrieval proxy, not RAGAS faithfulness or answer-relevancy scores. The benchmark includes two chart-reading cases for slides 14 and 18.

## Run framework-based answer evaluation

Install the optional dependencies once from the backend folder:

```powershell
python -m pip install -r evaluation/requirements.txt
```

Then run the smaller live RAGAS set (the tutor uses the configured text provider; RAGAS currently uses Groq as its judge and needs `GROQ_API_KEY`):

```powershell
python -m evaluation.run_ragas_evaluation --material-id YOUR_MATERIAL_ID
```

The default set scores eight answerable questions with RAGAS faithfulness, answer relevancy, context precision, and context recall. It also records whether answers cite the expected slide and whether five off-material answers explicitly flag lack of coverage. The latter two are deterministic checks, not RAGAS metrics. Results are saved to `evaluation/ragas_results.json`. Run `--help` to select a smaller set with `--case-ids` or choose a different output path.

The live run needs available quota for the configured tutor model and the Groq evaluator. If either API returns a rate-limit error, no full RAGAS result has been produced; retry after quota resets or set `GROQ_EVAL_MODEL` to another currently available Groq model. Do not substitute assumed values for missing scores.

To evaluate another upload, use its material ID. The same deck must be uploaded to the running app first so its collection exists in `chroma_db`.

## Manual answer and grounding review

Run each question through Tutor using the same material. For each case, record:

- **Answer supported:** yes/no. For answerable questions, check the expected facts. For off-material questions, pass only when the tutor clearly says the deck does not cover it or labels general knowledge separately.
- **Citation correct:** yes/no/not applicable. Check that each citation points to the expected slide and that the slide supports the cited claim.
- **Repeated question:** yes/no when evaluating quizzes separately.

Do not report the manual review as an automated RAGAS metric. Report counts and the review method with the result.

## Simulate the learner model

From the backend folder, run:

```powershell
python -m evaluation.simulate_learner_profiles
```

This deterministic check runs 100 seeded replicates for each of three synthetic learner profiles through the same BKT update function used by quiz answers and saves results to `evaluation/learner_simulation_results.json`. It reports estimated mastery changes under an explicit assumed practice effect. It is a simulation, not evidence of real student gains; it does not measure generated-question repetition.
