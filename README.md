# Synapse AI Adaptive Learning Companion

Synapse ingests course material, stores source locations with extracted content, and uses retrieved course passages in tutor answers and quizzes.

## Knowledge ingestion and grounding

- **PDF:** PyMuPDF extracts page text first. Pages with embedded images or substantial vector graphics are rendered and sent to Grok vision in the background; descriptions are added to the searchable collection afterward.
- **PowerPoint:** Text from slide shapes and grouped shapes is indexed first. Embedded pictures are later combined into labeled contact sheets for Grok vision; native chart titles, categories, and values are available immediately as text.
- **YouTube:** Available transcripts are divided into time-linked chunks. Topic discovery samples timestamped transcript segments across the video to keep model requests within token limits.
- Each extracted unit retains its source type and page, slide, or timestamp metadata in Chroma. The `/ask` route numbers retrieved passages; the tutor is instructed to cite supported claims, and the UI only displays links whose citation numbers appear in the answer.
- Material-mode answers distinguish source-backed content from any general explanation. General content is labeled as outside the uploaded material.

## Learner model

- Quiz answers update a per-topic and per-subtopic Bayesian Knowledge Tracing estimate (initial mastery 0.20; learn 0.15; guess 0.20; slip 0.10).
- The local profile persists in `backend/student_analytics/learner_state.json`; Adaptive quiz starts use prior mastery to choose easy, medium, or hard. The existing dashboard continues to show accuracy counts and now uses the estimated mastery for topic status.
- The current prototype uses one local learner profile and updates mastery from quiz answers, not tutor conversations. Synthetic multi-session results and their assumptions are documented in `backend/evaluation/results_report.md`.

### Visual extraction configuration

Quiz generation and figure descriptions use Grok through the xAI API. Set `XAI_API_KEY` in the backend environment; `GROK_TEXT_MODEL` and `GROK_VISION_MODEL` can select the respective models. Document Q&A, document topic extraction, and resume analysis use Groq via `GROQ_API_KEY`. All detected PDF figures and embedded PowerPoint pictures are analyzed; PowerPoint images are sent in batches of eight. Visual work is prepared with bounded workers (`VISION_CONCURRENCY`, default: 4), while actual Grok requests are serialized. Rate limits and temporary service availability errors are retried. If the key is missing or a request ultimately fails, text ingestion continues and the failure is logged.

Uploads are limited to 10 MB by default (`MAX_UPLOAD_SIZE_MB`), PDFs to 50 pages (`MAX_PDF_PAGES`), and five PDFs per anonymous browser profile (`MAX_PDF_UPLOADS_PER_STUDENT`). The upload counter uses `SYNAPSE_UPLOAD_DB_PATH` (default `data/upload_limits.sqlite3`). A browser profile is not a verified account; clearing its site data or using another browser creates a new profile ID. On Render, put this database and uploaded files on persistent storage if limits and materials must survive deployments. PDF pages are prepared with bounded workers (`VISION_CONCURRENCY`, default 4, maximum 8); actual Grok requests are serialized and remain associated with their original page. Successful figure descriptions are cached locally in `data/visual_cache` by image, surrounding text, source location, and model so an identical re-upload can reuse the description. The sentence-transformer embedding model is initialized once per backend process and reused. These local caches are not shared between hosted instances and may be lost on hosts with ephemeral filesystems.

## Known limitations

- Native PowerPoint text and chart data are extracted, but relationships in editable vector diagrams may not be fully described. Image-based figures and embedded pictures receive vision descriptions.
- Vision descriptions are model-generated and have not yet been measured for figure-caption accuracy.
- The benchmark currently reports source-location retrieval proxies and a small manual tutor spot check. It is not a complete RAGAS or DeepEval evaluation.

## Evaluation files

See [`backend/evaluation/README.md`](backend/evaluation/README.md) for the benchmark, retrieval scorer, results, and answer-review sheet.

## Resume Analyzer

The Career Intelligence workspace is available from the Synapse sidebar. It accepts PDF and DOCX resumes, extracts text locally, and uses Groq for structured analysis, job requirement descriptions, fact-preserving rewrites, and document topic extraction. Resume quality, ATS compatibility, and job match scores are deterministic and include component breakdowns. Resume analysis records and source files are stored in `data/resume_analyzer.sqlite3` and `data/resumes` by default. Set `SYNAPSE_RESUME_DB_PATH`, `SYNAPSE_RESUME_FILES_PATH`, and `MAX_RESUME_SIZE_MB` to customize storage and upload limits. The browser profile ID scopes record access; it is anonymous profile isolation rather than authenticated account security. Keep the storage directory private and persistent on hosted deployments.

The original PDF opens in the source viewer; DOCX files are preserved and offered as downloads because the browser cannot render DOCX natively. Analysis and page references are AI generated and should be verified against the original. The ATS score is an estimate, never a score from a real applicant tracking system. Resume analysis uses `GROQ_API_KEY` and `GROQ_RESUME_MODEL` (default `openai/gpt-oss-120b`); tutor and study features continue to use `XAI_API_KEY`.

Run locally from the project root in two terminals:

1. Backend: `cd backend` then `.venv\Scripts\python.exe -m uvicorn main:app --reload`
2. Frontend: `cd frontend` then `npm run dev`

On systems without the included Python environment, install `requirement.txt` into a virtual environment first. Configure `VITE_API_BASE` only when the API is not at `http://127.0.0.1:8000`.

## Chat with Documents

The sidebar's Chat with Documents page reuses the existing LangChain and Chroma retrieval workflow. Upload supported study or reference documents, ask questions grounded in retrieved passages, and open page citations in the uploaded source. Conversations persist in browser local storage. The backend's optional RAGAS evaluation scripts are documented in `backend/evaluation/README.md`. The original React and FastAPI interface remains available alongside the Streamlit interface.

## Streamlit interface and deployment

A Streamlit version of the six career and document modules is available in [`streamlit_frontend/`](streamlit_frontend/README.md). Streamlit Community Cloud hosts that Python interface; the FastAPI backend can run as the Docker Space packaged in `backend/`. The backend and Streamlit app share a private API token, and the backend uses `/data` for persistent storage when a Hugging Face Storage Bucket is attached.
