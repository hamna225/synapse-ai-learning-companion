# Synapse Streamlit interface

This folder contains the Streamlit interface for the existing Synapse FastAPI service. The React app remains in `frontend/` and is unchanged.

## Run locally

From this folder, install `requirements.txt`, then set `API_BASE_URL` to the running backend address (for example `http://127.0.0.1:8000`). Start the page with `streamlit run streamlit_app.py`.

For local development, the backend must be running from `backend/`. It also needs the provider keys used by the enabled features. Do not put API keys in this folder or commit them.

## Streamlit Community Cloud

1. Push this repository to GitHub, including this folder and the backend source.
2. In Streamlit Community Cloud, create an app from the repository and choose `streamlit_frontend/streamlit_app.py` as the entrypoint.
3. In the app's Advanced settings, add Streamlit secrets:

   ```toml
   API_BASE_URL = "https://YOUR-BACKEND-ADDRESS"
   SYNAPSE_API_TOKEN = "the-same-long-random-token-as-the-backend"
   ```

4. Deploy or reboot the Streamlit app.

Streamlit Cloud serves this interface only. The FastAPI backend must run at the `API_BASE_URL` you configure. Set `GROQ_API_KEY` and `XAI_API_KEY` as secrets on that backend host (xAI is used by visual analysis; Groq powers resume analysis, document Q&A, and topic extraction). The matching `SYNAPSE_API_TOKEN` protects API calls from unauthorized requests.

## Hugging Face backend Space

The backend is packaged as a Docker Space in `backend/`.

1. On Hugging Face, create a new **Docker Space** named `synapse-api`.
2. Install the Hugging Face Hub CLI on your computer if needed (`py -m pip install -U huggingface_hub`), then sign in with a Hugging Face **write** token using `hf auth login`.
3. From the project root, upload the backend folder to the Space (replace the account name):

   ```powershell
   hf upload YOUR_HF_USERNAME/synapse-api .\backend . --repo-type space
   ```

   This sends the backend source and its Docker setup. The backend's local database, uploaded files, and vector index folders are excluded by `backend/.gitignore`.

4. In the Space's **Settings → Variables and secrets**, add these as **secrets**:
   - `GROQ_API_KEY`
   - `XAI_API_KEY`
   - `SYNAPSE_API_TOKEN`

   Make a long random token locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Paste the same token into this Space and the Streamlit app's secrets. Do not paste it into chat or commit it.

5. Attach a Hugging Face Storage Bucket to the Space at `/data`. The backend is configured to store its resume records, uploaded documents, vector database, and model cache there. Without persistent storage, files on the Space's ordinary disk are lost when it restarts. [Hugging Face documents Docker Spaces, runtime secrets, and storage buckets here](https://huggingface.co/docs/hub/spaces-sdks-docker).
6. Wait for the Space to build. Its API address will be `https://YOUR_HF_USERNAME-synapse-api.hf.space`. Check that address in a browser; `/` should say the backend is online.
7. Set that address as `API_BASE_URL` in Streamlit Community Cloud secrets, together with the same `SYNAPSE_API_TOKEN`. Streamlit's deployment steps are in the [official guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app).

## Backend storage

Use persistent storage on the backend host. Otherwise uploaded resumes, study documents, Chroma indexes, and saved analysis history can disappear when the host restarts or redeploys. Point these backend settings to the host's persistent disk:

```text
SYNAPSE_RESUME_DB_PATH=/persistent/resume_analyzer.sqlite3
SYNAPSE_RESUME_FILES_PATH=/persistent/resumes
SYNAPSE_UPLOAD_DB_PATH=/persistent/upload_limits.sqlite3
SYNAPSE_MATERIALS_PATH=/persistent/uploaded_materials
SYNAPSE_CHROMA_DB_PATH=/persistent/chroma_db
SYNAPSE_LEARNER_PROFILE_PATH=/persistent/learner_state.json
```

The profile code shown in the sidebar lets a person reopen their anonymous analysis history. It is an access token, not authentication; keep it private. The selected document and current chat are kept in the active Streamlit session.

## API features used

- Resume upload, analysis, source download, history, matching, and rewrite: `/resumes` endpoints.
- Study material upload and source: `/sessions` and `/materials/{material_id}/source` endpoints.
- Grounded document questions and full-document topic extraction: `/ask` and `/topics`.
