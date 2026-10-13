# Synapse AI Adaptive Learning Companion

Synapse ingests course material, stores source locations with extracted content, and uses retrieved course passages in tutor answers and quizzes.

## Knowledge ingestion and grounding

- **PDF:** PyMuPDF extracts page text. Pages with embedded images or substantial vector graphics are rendered and sent to Groq vision for a concise figure description.
- **PowerPoint:** Text from slide shapes and grouped shapes is extracted. Embedded pictures are combined into a labeled contact sheet for Groq vision; native chart titles, categories, and values are extracted as text.
- **YouTube:** Available transcripts are divided into time-linked chunks. Topic discovery samples timestamped transcript segments across the video to keep model requests within token limits.
- Each extracted unit retains its source type and page, slide, or timestamp metadata in Chroma. The `/ask` route numbers retrieved passages; the tutor is instructed to cite supported claims, and the UI only displays links whose citation numbers appear in the answer.
- Material-mode answers distinguish source-backed content from any general explanation. General content is labeled as outside the uploaded material.

## Learner model

- Quiz answers update a per-topic and per-subtopic Bayesian Knowledge Tracing estimate (initial mastery 0.20; learn 0.15; guess 0.20; slip 0.10).
- The local profile persists in `backend/student_analytics/learner_state.json`; Adaptive quiz starts use prior mastery to choose easy, medium, or hard. The existing dashboard continues to show accuracy counts and now uses the estimated mastery for topic status.
- The current prototype uses one local learner profile and updates mastery from quiz answers, not tutor conversations. Synthetic multi-session results and their assumptions are documented in `backend/evaluation/results_report.md`.

### Visual extraction configuration

Visual descriptions use the Groq vision model `qwen/qwen3.8-27b` by default. Set `GROQ_VISION_MODEL` to override it and `VISION_MAX_VISUALS_PER_FILE` to change the per-file visual limit (default: 20). Images are sent to the configured Groq API. If the key is missing or a vision request fails, text ingestion continues and the failure is logged.

## Known limitations

- Native PowerPoint text and chart data are extracted, but relationships in editable vector diagrams may not be fully described. Image-based figures and embedded pictures receive vision descriptions.
- Vision descriptions are model-generated and have not yet been measured for figure-caption accuracy.
- The benchmark currently reports source-location retrieval proxies and a small manual tutor spot check. It is not a complete RAGAS or DeepEval evaluation.

## Evaluation files

See [`backend/evaluation/README.md`](backend/evaluation/README.md) for the benchmark, retrieval scorer, results, and answer-review sheet.
