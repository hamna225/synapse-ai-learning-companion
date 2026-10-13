# Evaluation results

**Run date:** 2026-10-12  
**Course material:** `Basics_of_Machine_Learning.pptx`  
**Material collection:** `material_58e6a8a98719`

## Source-location retrieval

The benchmark contains 22 answerable cases (17 content questions and 5 citation checks). It now includes chart questions for slides 14 and 18. The local Chroma retriever was evaluated at `k=5` by matching retrieved slide metadata against the expected slide in the benchmark.

| Metric | Result |
|---|---:|
| Mean source precision@5 | 0.182 |
| Mean source recall@5 | 0.909 |
| Expected slide found in top five | 20/22 (90.9%) |

This is a source-location retrieval proxy, not a RAGAS context-precision/recall score. It treats only the benchmark's expected slide as relevant, so the precision score is strict. Per-case results are in `retrieval_results.json`.

## Manual answer and citation spot check

The earlier 3/5 manual review is retained as historical pre-fix evidence only. It predates the citation-filtering and visual-extraction changes and is not a current system score. The user's later live checks included answers for slide 5, slide 6, slide 14, and slide 18; these are anecdotal examples, not a controlled or complete manual evaluation.

The spot check exposed citation noise: the tutor showed retrieved slides that were not cited in its answer. The UI now displays only source links whose citation numbers appear in the answer, preserving the original citation numbers.

Visual extraction has since been added for PDF pages with images/vector graphics, embedded PowerPoint pictures, and native chart data. The vision integration and source-location preservation are covered by mocked ingestion tests; real Groq vision accuracy has not been benchmarked yet.

## Framework-based answer and grounding metrics

**Evaluator follow-up:** The logged `ml03` retrieval ranked slide 6 fourth, but the Tutor prompt and evaluator previously truncated the context to three passages. The app and evaluator now both use the same top five and include each passage's slide/page label in the prompt. The Tutor prompt also now distinguishes citation indices from actual slide/page numbers and explicitly labels details not covered by the material. Earlier RAGAS scores below are pre-fix baselines; rerun the in-deck cases to measure the updated context behavior.

The first targeted post-fix rerun (`ml03`, `cite05`, `off03`) produced mean faithfulness **0.5000**, answer relevancy **0.8472**, context precision **0.5375**, and context recall **1.0000**. The `ml03` answer used slide 6 and cited passage `[4]`; `off03` stated the request was not covered before giving general code. `cite05` initially omitted an inline citation twice. A deterministic fallback now adds a citation only when a “which slide/page” answer's stated location exactly matches a retrieved source's metadata. The final live recheck generated “Slide 19 [1]”, scored faithfulness **1.0**, answer relevancy **0.8041**, context precision **0.75**, context recall **1.0**, and expected-slide citation hit **1/1**. Its output is in `ragas_cite05_final.json`. Across the rerun `ml03` and corrected `cite05` cases, faithfulness averages **1.0**, answer relevancy **0.8472**, context precision **0.5375**, context recall **1.0**, with citations matching **2/2**. The original broad RAGAS means above remain pre-fix baselines for the other cases; rerun them to obtain a fully post-fix aggregate.

RAGAS 0.4.3 is installed as an optional evaluation dependency. A completed two-case smoke run (`ml01`, `off01`) verified the scoring pipeline. It used one answerable question, so these values are a pipeline check, **not representative benchmark scores**:

| Smoke-test metric | Result |
|---|---:|
| Faithfulness | 0.7778 |
| Answer relevancy | 1.0000 |
| Context precision | 1.0000 |
| Context recall | 1.0000 |
| Expected-slide citation hit | 1/1 |
| Explicit off-material label found | 1/1 |

The off-material answer labeled its response as outside the uploaded material but also asserted a specific 2026 market-size figure without a verifiable source. The phrase-based label check alone does not verify that outside claim or establish a safe refusal. The smoke-test case outputs are saved in `ragas_quick_results.json`.

The next completed batch evaluated two more in-deck cases:

| Batch 1 metric | Result |
|---|---:|
| Faithfulness | 0.2917 |
| Answer relevancy | 0.8681 |
| Context precision | 0.5000 |
| Context recall | 0.5000 |
| Expected-slide citation hit | 1/2 |

The `ml03` case (“three main types of machine learning”) retrieved slides 2, 3, and 1 as its three contexts, missing expected slide 6. The tutor consequently labeled its answer as outside the uploaded material, and this case scored 0 for faithfulness, context precision, context recall, and citation hit. This points to a concrete retrieval/context-selection issue. The `ml06` case retrieved slide 9 and scored 0.5 faithfulness, 0.8459 answer relevancy, 1.0 context precision, and 1.0 context recall. Per-case results are in `ragas_batch1.json`.

The next two-case batch (`ml13`, `cite03`) scored mean faithfulness **1.0**, answer relevancy **0.8672**, context precision **1.0**, and context recall **1.0**. Both citations matched their expected slides (**2/2**) after the evaluator was corrected to recognize the Tutor's `【1】` citation format as well as `[1]`. Per-case results are in `ragas_batch2.json`.

Batch 3 (`cite05`, `chart14`) scored mean faithfulness **1.0**, answer relevancy **0.7830**, context precision **1.0**, and context recall **1.0**. Only one of the two answers matched its expected slide citation. `chart14` cited slide 14 correctly. For `cite05`, retrieval included slide 19, but the answer said “slide 1” and included no citation marker; count this as an answer/citation failure despite the RAGAS faithfulness score of 1.0. This shows the context metrics and automated faithfulness score do not guarantee correct slide numbering. Results are in `ragas_batch3.json`.

Batch 4 (`chart18`, `off02`) scored the chart answer at faithfulness **1.0**, answer relevancy **0.5830**, context precision **1.0**, and context recall **1.0**. The slide citation matched. The off-material answer explicitly labeled its content as outside the uploaded material (1/1 phrase check); this does not verify the external explanation's factual accuracy. Results are in `ragas_batch4.json`.

Across all eight in-deck cases (`ml01`, `ml03`, `ml06`, `ml13`, `cite03`, `cite05`, `chart14`, `chart18`), the combined per-case means are:

| RAGAS / grounding measure | Result |
|---|---:|
| Faithfulness | 0.7951 |
| Answer relevancy | 0.8275 |
| Context precision | 0.8750 |
| Context recall | 0.8750 |
| Expected-slide citation hit | 6/8 (75%) |

The default benchmark also has five off-material cases. The phrase-based flag check initially passed `off01` and `off02`, but it does not test factual correctness of outside information. The earlier full all-in-one run was interrupted, but the required in-deck set has since completed in batches. The remaining cases are being checked individually.

Batch 5 completed two more off-material cases: `off04` (current stock prices) was explicitly identified as not covered, while `off03` (Random Forest code for Iris) received a full code answer without an outside-material warning (**1/2 flagged**). The latter is a clear unsupported-query handling miss. No RAGAS content metrics apply to this off-material-only batch. Results are in `ragas_batch5.json`.

The final case, `off05` (transformer self-attention), was labeled as a general explanation outside the uploaded material. Across all five off-material tests, **4/5 answers contained an explicit outside-material label**. This deterministic phrase check is not an automated factuality metric: `off01` still gave an unsupported market-size estimate, and `off03` failed to flag uncovered content. `ragas_batch6.json` contains the last case. All 13 cases in the small RAGAS suite have now been run across the saved batch files.

## Still not measured

- Real-student learning gains across multiple sessions
- Repetition rate for questions from the live generator across assessments

Do not report these as evaluated until they are tested. The full benchmark, per-case retrieval results, and manual review sheet are in this folder.

## Persistent learner model update

The quiz-answer flow now updates a local per-topic and per-subtopic Bayesian Knowledge Tracing (BKT) estimate after each answer. It persists to `backend/student_analytics/learner_state.json`, survives backend restarts, and initializes Adaptive quizzes at easy, medium, or hard using prior topic mastery. The dashboard reads this saved profile while retaining raw accuracy counts.

The deterministic synthetic run is in `learner_simulation_results.json` and can be regenerated with `python -m evaluation.simulate_learner_profiles` from the backend folder. It runs 100 seeded replicates for each of three synthetic student profiles; each replicate has five sessions of five questions, with the weakest estimated topic selected per session. Under the script's stated assumption that focused practice raises a topic's synthetic response probability by four percentage points per session, mean estimated mastery changes were 60.0 points (balanced), 76.6 (advanced), and 36.5 (needs foundations). Mean simulated accuracy was 52.4%, 74.4%, and 33.8%, respectively.

These are simulation outputs from assumed answer probabilities, **not observed student learning gains**. The run does not call the live question generator, so question repetition rate remains unmeasured. The current learner profile is local and single-user; tutor conversations do not yet update mastery.
