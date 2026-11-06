"""Streamlit interface for Synapse's existing FastAPI career and document tools."""

from __future__ import annotations

import os
import uuid
from datetime import datetime

import requests
import streamlit as st


st.set_page_config(page_title="Synapse · Career AI", page_icon="🧠", layout="wide")

try:
    configured_api = st.secrets.get("API_BASE_URL", "")
    configured_token = st.secrets.get("SYNAPSE_API_TOKEN", "")
except Exception:
    configured_api = ""
    configured_token = ""
API = (os.getenv("SYNAPSE_API_URL") or configured_api).strip().rstrip("/")
API_TOKEN = os.getenv("SYNAPSE_API_TOKEN") or configured_token
OWNER_KEY = "synapse_owner"
if OWNER_KEY not in st.session_state:
    st.session_state[OWNER_KEY] = str(uuid.uuid4())
if "resume" not in st.session_state:
    st.session_state.resume = None
if "material" not in st.session_state:
    st.session_state.material = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "topics" not in st.session_state:
    st.session_state.topics = []
if "history_loaded" not in st.session_state:
    st.session_state.history_loaded = False


def api_request(method: str, path: str, *, timeout: int = 90, **kwargs):
    if not API:
        st.error("Connect the backend first: add API_BASE_URL to Streamlit secrets.")
        return None
    try:
        headers = dict(kwargs.pop("headers", {}))
        if API_TOKEN:
            headers["Authorization"] = f"Bearer {API_TOKEN}"
        response = requests.request(method, f"{API}{path}", headers=headers, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        st.error(f"Could not reach the Synapse backend: {exc}")
        return None
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        st.error(f"Backend error ({response.status_code}): {detail}")
        return None
    return response


def api_json(method: str, path: str, **kwargs):
    response = api_request(method, path, **kwargs)
    if response is None:
        return None
    try:
        return response.json()
    except ValueError:
        st.error("The backend returned an unreadable response.")
        return None


def owner_params():
    return {"owner": st.session_state[OWNER_KEY]}


def restore_profile():
    value = st.session_state.get("profile_input", "").strip()
    if value and value != st.session_state[OWNER_KEY]:
        st.session_state[OWNER_KEY] = value
        st.session_state.history_loaded = False
        st.session_state.resume = None
        st.session_state.pop("learning_session", None)
        st.session_state.material = None
        st.session_state.messages = []
        st.session_state.topics = []


def history_rows():
    return api_json("GET", "/resumes", params=owner_params()) or []


def load_resume(resume_id: str):
    data = api_json("GET", f"/resumes/{resume_id}", params=owner_params())
    if data:
        st.session_state.resume = data
        st.rerun()


def nice(value: str) -> str:
    return value.replace("_", " ").title()


def render_list(title: str, values, empty="Nothing identified in the resume text."):
    with st.container(border=True):
        st.subheader(title)
        if values:
            for item in values:
                if isinstance(item, dict):
                    heading = item.get("role") or item.get("title") or item.get("topic")
                    body = item.get("details") or item.get("evidence") or item.get("description")
                    st.markdown(f"**{heading}**" if heading else "")
                    if body:
                        st.write(body)
                    if item.get("page"):
                        st.caption(f"Page {item['page']}")
                    if not heading and not body:
                        st.write(" · ".join(f"{k}: {v}" for k, v in item.items()))
                else:
                    st.markdown(f"- {item}")
        else:
            st.caption(empty)


def render_breakdown(breakdown):
    if not breakdown:
        return
    with st.expander("Scoring breakdown"):
        for label, detail in breakdown.items():
            earned = detail.get("earned")
            earned_text = "Not available" if earned is None else f"{earned}%"
            st.write(f"**{label}:** {earned_text} · weight {detail.get('weight', 0)}%")


def score_card(label: str, value, breakdown=None, note=None):
    with st.container(border=True):
        st.metric(label, f"{value}/100" if isinstance(value, (int, float)) else "Not calculated")
        if note:
            st.caption(note)
        render_breakdown(breakdown)


def upload_resume():
    uploaded = st.file_uploader("Upload a PDF or DOCX resume", type=["pdf", "docx"], key="resume_upload")
    if uploaded and st.button("Analyze resume", type="primary", key="analyze_resume"):
        with st.spinner("Reading and analyzing your resume…"):
            result = api_json(
                "POST", "/resumes", data=owner_params(),
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")},
                timeout=180,
            )
        if result:
            st.session_state.resume = result
            st.success("Resume analyzed and saved.")
            st.rerun()


def show_analyzer(resume):
    st.title("Resume Analyzer")
    st.caption("Review extracted details, section gaps, and document evidence.")
    upload_resume()
    if not resume:
        st.info("Upload a resume or open a saved analysis from Analysis History.")
        return
    analysis = resume.get("analysis", {})
    left, right = st.columns(2)
    with left:
        score_card("Resume Quality", analysis.get("quality_score"), analysis.get("quality_breakdown"))
    with right:
        score_card("ATS Compatibility", analysis.get("ats_score"), analysis.get("ats_breakdown"), analysis.get("ats_disclaimer"))
    st.caption(f"{resume.get('filename', 'Resume')} · {resume.get('text_length', 0):,} readable characters")

    fields = ["contact", "summary", "education", "technical_skills", "experience", "projects", "certifications", "languages"]
    for start in range(0, len(fields), 2):
        columns = st.columns(2)
        for column, key in zip(columns, fields[start:start + 2]):
            review = analysis.get("section_reviews", {}).get(key, {})
            value = analysis.get(key, [])
            if key == "contact":
                contact = analysis.get("contact_info", {})
                value = [f"{nice(kind)}: {entry}" for kind, items in contact.items() for entry in items]
            elif key == "summary":
                value = [analysis.get("summary", "")]
            with column:
                render_list(nice(key), value)
                st.caption("Found in resume" if review.get("present") else "Not found in resume text")
                if review.get("recommendation"):
                    st.caption(review["recommendation"])
    if analysis.get("missing_information"):
        render_list("Information not found in the document", analysis["missing_information"])
    with st.expander("Original resume"):
        if st.button("Prepare original download", key=f"source-{resume['id']}"):
            source = api_request("GET", f"/resumes/{resume['id']}/source", params=owner_params())
            if source:
                st.download_button("Download original resume", source.content, file_name=resume["filename"], mime=resume.get("mime", "application/octet-stream"), key=f"download-{resume['id']}")


def show_ats(resume):
    st.title("ATS Checker")
    st.caption("A transparent estimate based on extracted text, headings, contact details, bullets, and readable content.")
    if not resume:
        st.info("Upload a resume from Resume Analyzer first.")
        upload_resume()
        return
    analysis = resume.get("analysis", {})
    a, b = st.columns(2)
    with a:
        score_card("ATS Compatibility", analysis.get("ats_score"), analysis.get("ats_breakdown"), analysis.get("ats_disclaimer"))
    with b:
        score_card("Resume Quality", analysis.get("quality_score"), analysis.get("quality_breakdown"))
    render_list("Formatting and parsing warnings", analysis.get("formatting_warnings", []), "No formatting warnings were identified.")


def show_matcher(resume):
    st.title("Job Matcher & Skill Gaps")
    st.caption("Compare resume evidence with a target role. Skills absent from the text are labeled ‘not evidenced,’ not assumed absent.")
    if not resume:
        st.info("Upload a resume from Resume Analyzer or open one from Analysis History.")
        upload_resume()
        return
    analysis = resume.get("analysis", {})
    old_match = analysis.get("job_match", {})
    with st.form("job_match_form"):
        role = st.text_input("Target role", value=analysis.get("target_role", ""), placeholder="e.g. Data analyst")
        description = st.text_area("Job description", value=analysis.get("job_description", ""), height=200, placeholder="Paste the full job description…")
        submitted = st.form_submit_button("Analyze match", type="primary")
    if submitted:
        if len(description.strip()) < 50:
            st.warning("Paste a job description with at least 50 characters.")
        else:
            result = api_json("POST", f"/resumes/{resume['id']}/match", json={**owner_params(), "target_role": role, "job_description": description}, timeout=120)
            if result:
                loaded = api_json("GET", f"/resumes/{resume['id']}", params=owner_params())
                if loaded:
                    st.session_state.resume = loaded
                    st.success("Job comparison saved.")
                    st.rerun()
    match = old_match
    if match:
        score_card("Job Match", match.get("match_percentage"), match.get("score_breakdown"))
        left, right = st.columns(2)
        with left:
            render_list("Skills evidenced in resume", match.get("matching_skills", []))
        with right:
            render_list("Skills required but not evidenced", match.get("missing_skills", []), "No recognized skill terms were identified as missing.")
        st.caption("Not evidenced means the resume text does not show the skill; it does not establish that you lack it.")
        for key, title in [("required_qualifications", "Required qualifications"), ("relevant_projects", "Relevant projects"), ("improvements", "Suggested resume changes")]:
            render_list(title, match.get(key, []))
        for key, title in [("skill_development", "Recommended skills to develop"), ("project_ideas", "Project ideas to build evidence"), ("learning_paths", "Suggested learning paths")]:
            render_list(title, analysis.get(key, []))


def show_builder(resume):
    st.title("Resume Builder")
    st.caption("Get a suggested rewrite. Your uploaded file is never silently overwritten.")
    if not resume:
        st.info("Upload a resume from Resume Analyzer or open one from Analysis History.")
        upload_resume()
        return
    analysis = resume.get("analysis", {})
    choices = {
        "Professional summary": analysis.get("summary", ""),
        "Technical skills": ", ".join(analysis.get("technical_skills", [])),
        "Project description": "\n".join(str(x) for x in analysis.get("projects", [])),
        "Work experience bullet": "\n\n".join(str(x.get("details") or x.get("evidence") or "") for x in analysis.get("experience", []) if isinstance(x, dict)),
        "Resume headline": analysis.get("resume_headline", ""),
    }
    target = st.selectbox("Section to improve", list(choices))
    source = st.text_area("Original content", value=choices[target], height=180, placeholder="Paste or edit the section content…")
    if st.button("Suggest a rewrite", type="primary"):
        if len(source.strip()) < 10:
            st.warning("Enter at least 10 characters to improve.")
        else:
            result = api_json("POST", f"/resumes/{resume['id']}/improve", json={**owner_params(), "section": source}, timeout=120)
            if result:
                st.session_state.builder_result = result.get("improved_text", "")
    if st.session_state.get("builder_result"):
        st.subheader("Suggested content")
        st.write(st.session_state.builder_result)
        st.caption("The rewrite is a draft. Review it before use; the uploaded file stays unchanged.")
        st.download_button("Download suggestion", st.session_state.builder_result, file_name="resume-section-suggestion.txt", mime="text/plain")


def show_history(resume):
    st.title("Analysis History")
    st.caption("Each upload is saved as a separate resume version.")
    rows = history_rows()
    if not rows:
        st.info("No saved analyses yet. Upload a resume from Resume Analyzer.")
        return
    for row in rows:
        scores = row.get("analysis", {})
        when = row.get("created_at", "")
        try:
            when = datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone().strftime("%b %d, %Y · %I:%M %p")
        except (ValueError, AttributeError):
            pass
        with st.container(border=True):
            cols = st.columns([4, 2, 2, 1, 1])
            cols[0].markdown(f"**{row.get('filename', 'Resume')}**  \n{when}")
            cols[1].write(f"Quality {scores.get('quality_score', '—')}/100")
            cols[2].write(f"ATS {scores.get('ats_score', '—')}/100")
            match = scores.get("job_match") or {}
            cols[3].write(f"Job {match['match_percentage']}/100" if match.get("match_percentage") is not None else "Job —")
            if cols[4].button("Open", key=f"open-{row['id']}"):
                load_resume(row["id"])
            if cols[0].button("Delete this upload", key=f"delete-{row['id']}"):
                deleted = api_json("DELETE", f"/resumes/{row['id']}", params=owner_params())
                if deleted:
                    if resume and resume.get("id") == row["id"]:
                        st.session_state.resume = None
                    st.rerun()


def show_documents():
    st.title("Chat with Documents")
    st.caption("Ask questions grounded in uploaded documents. Sources remain attached to their page or slide.")
    if not API:
        st.info("Connect the backend first by setting API_BASE_URL in Streamlit secrets.")
        return
    student_id = st.session_state[OWNER_KEY]
    if "learning_session" not in st.session_state:
        session = api_json("POST", "/sessions", json={"student_id": student_id})
        if session:
            st.session_state.learning_session = session["session_id"]
    upload = st.file_uploader("Upload a PDF, PPT, or PPTX", type=["pdf", "ppt", "pptx"], key="material_upload")
    if upload and st.button("Add learning material", type="primary"):
        session_id = st.session_state.get("learning_session")
        if session_id:
            with st.spinner("Reading and indexing your document…"):
                result = api_json("POST", f"/sessions/{session_id}/materials", files={"file": (upload.name, upload.getvalue(), upload.type or "application/octet-stream")}, timeout=300)
            if result:
                st.session_state.material = result
                st.session_state.messages = []
                st.session_state.topics = []
                st.success(f"{upload.name} is ready for text-based study.")
                st.rerun()
    material = st.session_state.get("material")
    if not material:
        return
    material_id = material.get("material_id") or material.get("id")
    material_name = material.get("material_name") or material.get("filename") or "Learning material"
    st.info(f"📚 {material_name} is ready")
    if st.button("Find all topics in this document"):
        with st.spinner("Reviewing the full document…"):
            result = api_json("POST", "/topics", json={"material_id": material_id}, timeout=240)
        if result:
            st.session_state.topics = result.get("topics", [])
    if st.session_state.topics:
        with st.expander("Topics in this document", expanded=True):
            for topic in st.session_state.topics:
                st.markdown(f"**{topic.get('topic', '')}**")
                if topic.get("subtopics"):
                    st.caption(" · ".join(topic["subtopics"]))
    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            for source in item.get("sources", []):
                source_url = source.get("url", "")
                if source_url.startswith("/"):
                    source_url = f"{API}{source_url}"
                st.markdown(f"[{source.get('number', '')}. {source.get('label', 'Source')}]({source_url})")
    question = st.chat_input("Ask a question about your document")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching your material…"):
                result = api_json("POST", "/ask", json={"material_id": material_id, "question": question}, timeout=180)
            if result:
                answer = result.get("answer", "")
                st.markdown(answer)
                sources = result.get("sources", [])
                for source in sources:
                    source_url = source.get("url", "")
                    if source_url.startswith("/"):
                        source_url = f"{API}{source_url}"
                    st.markdown(f"[{source.get('number', '')}. {source.get('label', 'Source')}]({source_url})")
                st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})


st.markdown("""
<style>
    .block-container { max-width: 1180px; padding-top: 2rem; }
    [data-testid="stSidebar"] { background: #f6f7fb; }
    h1, h2, h3 { letter-spacing: -0.025em; }
    div[data-testid="stMetric"] { background: #f7f6ff; border: 1px solid #e7e2ff; padding: 1rem; border-radius: 14px; }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("🧠 Synapse")
st.sidebar.caption("CAREER INTELLIGENCE")
page = st.sidebar.radio("Modules", ["Resume Analyzer", "Chat with Documents", "ATS Checker", "Job Matcher", "Resume Builder", "Analysis History"], label_visibility="collapsed")
with st.sidebar.expander("Profile code"):
    if "profile_input" not in st.session_state:
        st.session_state.profile_input = st.session_state[OWNER_KEY]
    st.text_input("Save this code to reopen your analyses", key="profile_input", on_change=restore_profile)
    st.caption("This code identifies your private browser profile. Keep it private; it is not a login password.")
if API:
    st.sidebar.caption("Backend URL configured")
else:
    st.sidebar.warning("Add API_BASE_URL in Streamlit secrets")

if API and not st.session_state.history_loaded:
    rows = history_rows()
    if rows:
        latest = api_json("GET", f"/resumes/{rows[0]['id']}", params=owner_params())
        if latest:
            st.session_state.resume = latest
    st.session_state.history_loaded = True

resume = st.session_state.get("resume")
if page == "Resume Analyzer":
    show_analyzer(resume)
elif page == "ATS Checker":
    show_ats(resume)
elif page == "Job Matcher":
    show_matcher(resume)
elif page == "Resume Builder":
    show_builder(resume)
elif page == "Analysis History":
    show_history(resume)
else:
    show_documents()
