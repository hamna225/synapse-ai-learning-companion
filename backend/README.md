---
title: Synapse Career AI API
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
---

# Synapse FastAPI backend

This Docker Space runs the FastAPI API consumed by the Streamlit interface. Add runtime secrets in **Settings → Variables and secrets** before starting the Space:

- `SYNAPSE_API_TOKEN`: a long random shared token. Set the same value in Streamlit Community Cloud secrets.
- `GROQ_API_KEY`: used for resume analysis, job matching, resume rewriting, document Q&A, and topic extraction.
- `XAI_API_KEY`: used for visual analysis and quiz generation.

The container stores analysis databases, uploaded files, Chroma indexes, and model cache below `/data`. Attach a Hugging Face Storage Bucket mounted at `/data` to retain them across restarts. Space-local disk is temporary.

The health endpoint is `https://<space-subdomain>.hf.space/`. Other API routes require an `Authorization: Bearer <SYNAPSE_API_TOKEN>` header. The Streamlit app adds this header from its secrets.
