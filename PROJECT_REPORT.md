# Synapse AI Learning Companion — Project Report

**Review date:** 13 October 2026  
**Repository:** `synapse-ai-learning-companion`  
**Purpose:** Snapshot of the implementation and its current readiness for a public student-facing deployment.

## Executive summary

Synapse is a working prototype of an AI study companion. It has a React/Vite frontend and a FastAPI backend, ingests PDF and PowerPoint files plus transcript-enabled YouTube videos, stores source-linked chunks in Chroma, and provides tutor answers, quizzes, subjective practice material, and a learning dashboard. The quiz flow updates a Bayesian Knowledge Tracing (BKT) profile and adapts later quiz difficulty.

The most important limitation for hosting it for multiple students is data and account isolation. The learner profile is one local JSON file shared by the backend, quiz sessions and question-history are held in process memory, and uploaded files and Chroma data are on the local filesystem. These choices are suitable for a single-user/local prototype, but can lose or mix student state on a hosted multi-user service. Authentication, per-user authorization, managed database/object storage, resource limits, and production monitoring are not present in the inspected code.

The configured AI provider is now **Grok through xAI** for tutoring, assessment generation, and figure extraction. The app also has a five-PDF limit keyed to an anonymous browser profile; it does not provide verified student accounts.

## Product and implemented features

### Learning material ingestion

- **PDF:** extracts text by page and attempts to describe pages containing embedded images or substantial vector drawings using a vision model. Page numbers are retained in document metadata.
- **PowerPoint:** extracts slide text, embedded images, and native chart information; slide numbers are retained. Embedded images are described through the configured vision provider.
- **YouTube:** obtains an available transcript and creates timestamped transcript chunks. It prefers English and otherwise uses the first available transcript.
- Uploaded document chunks are split/embedded and saved to a Chroma collection keyed by material ID. YouTube transcript chunks are also saved to Chroma.

### Tutor and grounding

- `/ask` retrieves up to five relevant chunks from a material collection and asks the model to answer using the provided course passages.
- The tutor prompt distinguishes course-supported content from general explanation. Tutor responses include source references, and the frontend filters displayed source links to citation numbers actually present in the answer.
- PDF/source citations link to the uploaded file endpoint with page navigation. YouTube citations can link to video timestamps.
- The evaluation report records both successful citation examples and remaining cases where citations or unsupported-content handling failed. This is a meaningful feature, but it is not a guarantee that every model response is supported or correctly cited.

### Adaptive assessment and learner analytics

- Quiz start generates a scoped MCQ quiz; answers are graded and the next question difficulty can adapt based on performance.
- Per-material duplicate detection uses normalized text and similarity matching. Its history is kept in backend memory and resets when the API process restarts.
- Every answered quiz question updates per-topic and per-subtopic BKT mastery using fixed initial mastery/learn/guess/slip parameters.
- The dashboard reports question counts, accuracy, topic results, and mastery. Starting difficulty uses existing topic history where available.
- The project includes subjective question/answer generation and PDF download functionality in the frontend.

### Frontend and deployment configuration

- Main frontend: React 19, Vite, Axios, and jsPDF, in `frontend/`.
- Backend: FastAPI, LangChain, Chroma, HuggingFace sentence-transformer embeddings, PyMuPDF, python-pptx, Pillow, and Groq SDK integrations.
- `netlify.toml` builds and publishes `frontend/dist`.
- The backend is structured for a separate Python host such as Render; it is not served by Netlify's static frontend deployment.
- `VITE_API_BASE` lets the frontend target a hosted API. `FRONTEND_ORIGINS` configures allowed frontend origins for CORS.
- `.gitignore` excludes secrets, local Chroma data, uploaded materials, caches, and local learner state. `.env.example` documents Groq-oriented configuration.

## API surface found in the code

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Basic health response |
| POST | `/sessions` | Create a learning session identifier |
| POST | `/sessions/{session_id}/materials` | Upload and process PDF/PPT/PPTX |
| POST | `/sessions/{session_id}/youtube` | Ingest a YouTube transcript |
| GET | `/materials/{material_id}/source` | Serve/preview an uploaded source |
| POST | `/ask` | Retrieve course context and answer a tutor question |
| POST | `/topics` | Discover topics from a material |
| POST | `/generate-subjective` | Generate subjective study questions/answers |
| POST | `/quiz/start` | Start an adaptive quiz |
| POST | `/quiz/answer` | Grade an answer and advance the quiz |
| GET | `/quiz/result/{quiz_id}` | Retrieve a completed quiz result |
| GET | `/dashboard` | Return learner analytics |

The session endpoint issues an ID, but inspected backend code does not authenticate a student or enforce ownership of that ID. Treat it as a prototype session identifier rather than account security.

## Current learner-data and hosting behavior

| Data | Current storage | Consequence when hosted |
|---|---|---|
| Quiz sessions | Python process memory | Lost on restart/redeploy; not shared across multiple API instances |
| Duplicate-question history | Python process memory by material | Resets on restart and is not durable across instances |
| Learner mastery/history | One JSON file (`backend/student_analytics/learner_state.json`) | Shared local profile rather than per-student accounts; may be lost on ephemeral storage |
| Chroma vectors | Local `chroma_db/` directory | Requires persistent storage or managed vector database; ephemeral host filesystems can discard it |
| Uploaded files | Local `uploaded_materials/` directory | Requires persistent/object storage and access controls for student use |
| Tutor conversation history | Browser `localStorage` | Browser/device-local; not synced to accounts or other devices |

The current implementation should not be presented as multi-user durable storage until those concerns are addressed. Render Free is ephemeral and sleeps after inactivity; a restart or new instance can therefore expose these storage limitations. The project report makes no claim that a paid host alone fixes data persistence or student isolation.

## AI provider and cost readiness

- Tutor, assessment, and figure analysis use the xAI-compatible `ChatOpenAI` client, configurable with `GROK_TEXT_MODEL` and `GROK_VISION_MODEL`.
- The RAGAS evaluator documentation expects Groq credentials/model configuration.
- `.env.example` uses `XAI_API_KEY` for the application. `GROQ_API_KEY` remains optional for the RAGAS evaluator only.
- AI spend is variable with input/output tokens, number of student requests, document/figure processing, retries, and model choice. No hard per-user or global usage quota was found in the reviewed code, so usage caps and provider-side budget alerts should precede a public launch.

## Evaluation evidence in the repository

The saved evaluation report is explicitly small and course-specific. It documents:

- Retrieval proxy on 22 answerable/citation cases: expected slide in top five for 20/22 (90.9%), mean source precision@5 0.182 and source recall@5 0.909. This is a source-location proxy, not a RAGAS context metric.
- RAGAS measurements across eight in-material cases, saved as batches: faithfulness 0.7951, answer relevancy 0.8275, context precision 0.8750, context recall 0.8750; expected-slide citation hit 6/8 (75%).
- Off-material handling phrase check: 4/5 cases contained an explicit outside-material label; the report notes this did not guarantee factual accuracy or safe refusal.
- A synthetic BKT simulation across three assumed student profiles. The report clearly labels it as simulated and not evidence of real student learning gains.
- Live question repetition rate across assessments and real-student multi-session gains are listed as not measured.

These are existing saved results from the evaluation report, not newly executed checks for this project snapshot. Some RAGAS cases are batch runs and the report calls out pre-fix results, remaining citation misses, and limitations. They should be described with those caveats in any public presentation.

## Current risks and gaps, in priority order

### Critical before onboarding real students

1. **Account and data isolation:** add authentication and authorize every material, source, quiz, and learner-data operation against the signed-in student. Current session IDs are not a substitute for authorization.
2. **Durable multi-user storage:** move learner profiles and quiz records to a database; store uploads in durable object storage; configure persistent/managed vector storage and backup/restore. Scope each record and vector collection to an owner.
3. **Upload safety and resource limits:** validate file signatures as well as extensions; enforce upload size, page/slide, extraction time, and request limits; handle malformed/oversized documents safely.
4. **Operational controls:** configure HTTPS, secrets in the host's environment settings, rate limiting, spend alerts/quotas, structured error reporting, health/readiness checks, and backups.

### High value next

5. **Provider verification:** verify Grok text and image requests against the configured xAI account and preserve the existing API response shapes.
6. **Assessment reliability:** persist question fingerprints, track repetition by student/material across deployments, validate question schema and answer keys, and retain cited feedback with source metadata.
7. **Grounding and refusals:** improve off-material refusal behavior and validate each displayed citation against its actual source location, not just a citation marker. Evaluate with more varied materials and independently reviewed cases.
8. **Cross-platform source preview:** PowerPoint-to-PDF preview uses Microsoft Office automation on Windows; the code returns HTTP 501 when the COM dependencies are unavailable. Hosted Linux deployments need a different conversion route or a clear download fallback.
9. **Privacy and product readiness:** add data-retention/deletion controls and a clear privacy notice before storing student uploads or learning records.

### Nice to have

10. Expand accessibility/mobile and browser testing, show processing progress and retry states, add user-visible feedback reporting, and provide service monitoring dashboards.
11. Clarify or remove the duplicate `backend/frontend/` starter frontend only after confirming it is not intentionally used. The Netlify configuration in the repository builds `frontend/`.

## Verification status

- Existing automated tests are in `backend/tests/` for quiz parsing/scoring, learner-profile persistence, and visual-ingestion behavior.
- Existing evaluation and test result files are documented above.
- No tests or builds were run while preparing this report; this is a source/documentation review and should not be read as a fresh pass of the current checkout.
- Git reported a clean `main` branch tracking `origin/main` at the time of review.

## Recommended next implementation sequence

1. Decide whether this is a private pilot or a public multi-student service; keep public access closed until account isolation and storage design are ready.
2. Add an account/ownership layer while preserving existing routes and UI, then move learner and quiz data to durable per-user storage.
3. Move uploads to durable object storage and decide how Chroma collections will persist and be isolated.
4. Add upload, request, and AI usage limits; configure logs, error monitoring, backups, and a privacy/deletion workflow.
5. Verify the Grok migration with backend tests, frontend lint/build, and focused API smoke tests.
6. Re-run the complete evaluation suite after provider or retrieval changes, and report measured results with the dataset, case count, run date, and caveats.

## Overall assessment

The repository is a substantial prototype with broad feature coverage and real evaluation artifacts. It demonstrates the core learning workflow, but its current storage and session design is local and single-profile oriented. It is suitable for a controlled demo or private pilot with disposable data; it is not yet ready to promise secure, persistent, multi-student service. The highest-impact work is infrastructure and account isolation before additional AI features.
