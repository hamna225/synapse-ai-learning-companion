import json

import pymupdf

import main
import resume_analyzer as analyzer


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def invoke(self, prompt):
        if prompt.startswith("Compare this resume"):
            return FakeResponse(json.dumps({"match_percentage": 72, "matching_skills": ["Python"], "missing_skills": ["Kubernetes"], "relevant_experience": [], "keyword_match": ["Python"], "improvements": ["Add a relevant project"]}))
        if prompt.startswith("Rewrite the user-provided"):
            return FakeResponse("Built a Python service with clear documentation.")
        return FakeResponse(json.dumps({"summary": "Python developer", "technical_skills": ["Python"], "soft_skills": [], "education": [], "experience": [{"role": "Developer", "organization": "Acme", "dates": "2024", "details": "Built services", "evidence": "Built services", "page": 1}], "projects": [], "certifications": [], "languages": [], "tools": [], "strengths": ["Python experience"], "weaknesses": [], "missing_information": [], "suggestions": [], "recommended_roles": ["Software developer"], "skill_development": [], "project_ideas": [], "experience_gaps": [], "learning_paths": [], "quality_score": 180, "ats_score": -4, "formatting_warnings": [], "keyword_coverage": []}))


def test_pdf_text_extraction_and_structured_ai_validation(monkeypatch, tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Python developer with experience building useful software projects and services.")
    path = tmp_path / "resume.pdf"
    doc.save(path)
    doc.close()
    extracted = analyzer.text_from_file(path, ".pdf")
    assert "[Page 1]" in extracted and "Python developer" in extracted
    monkeypatch.setattr(analyzer, "get_text_model", lambda **kwargs: FakeModel())
    result = analyzer.analyze(extracted)
    assert result["technical_skills"] == ["Python"]
    assert 0 <= result["quality_score"] <= 100
    assert sum(item["weight"] for item in result["quality_breakdown"].values()) == 100
    assert result["ats_score"] > 0
    assert "actual applicant tracking system" in result["ats_disclaimer"]


def test_match_improve_history_source_and_owner_isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(analyzer, "DB", str(tmp_path / "resumes.sqlite3"))
    monkeypatch.setattr(analyzer, "FILES", tmp_path / "files")
    monkeypatch.setattr(analyzer, "get_text_model", lambda **kwargs: FakeModel())
    analyzer.FILES.mkdir()
    source = analyzer.FILES / "record.pdf"
    source.write_bytes(b"%PDF preserved source")
    with analyzer.connect() as con:
        con.execute("INSERT INTO resumes VALUES (?,?,?,?,?,?,?,?)", ("id-1", "owner-a", "resume.pdf", str(source), "application/pdf", "Python experience", json.dumps({"quality_score": 80}), "2026-01-01T00:00:00+00:00"))
    with analyzer.connect() as con:
        assert analyzer.owned_resume(con, "id-1", "owner-a")["filename"] == "resume.pdf"
        try:
            analyzer.owned_resume(con, "id-1", "owner-b")
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 404
        else:
            raise AssertionError("A different browser profile accessed the resume")
    match = analyzer.match_job("id-1", analyzer.MatchRequest(owner="owner-a", job_description="We need a Python engineer with experience designing and building reliable software products and projects."))
    assert 0 <= match["match_percentage"] <= 100
    assert match["score_breakdown"] is not None
    rewritten = analyzer.improve("id-1", analyzer.ImproveRequest(owner="owner-a", section="I built a Python service for users."))
    assert rewritten["improved_text"].startswith("Built a Python")
    assert analyzer.history("owner-a")[0]["filename"] == "resume.pdf"
    assert analyzer.source("id-1", "owner-a").path == str(source)
    assert analyzer.delete_resume("id-1", "owner-a") == {"deleted": True}
    assert not source.exists()


def test_resume_routes_are_registered_and_extraction_rejects_unreadable_pdf(tmp_path):
    assert {"/resumes", "/resumes/{resume_id}/match", "/resumes/{resume_id}/improve", "/resumes/{resume_id}/source"}.issubset(main.app.openapi()["paths"])
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF broken")
    try:
        analyzer.text_from_file(path, ".pdf")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("Malformed PDF should have been rejected")


def test_education_fallback_and_phone_filter():
    text = "EDUCATION\nBachelor of Science, Computer Science\nUniversity of Agriculture Faislabad (2023-2027)\nSKILLS\nPython"
    education = analyzer.extract_education_lines(text)
    assert "Bachelor of Science, Computer Science" in education
    assert "University of Agriculture Faislabad (2023-2027)" in education
    assert analyzer.extract_phone_numbers(text) == []
    assert analyzer.extract_phone_numbers("Call +92 300 1234567") == ["+92 300 1234567"]


def test_resume_headline_is_extracted_verbatim_from_top_lines():
    text = "Ayesha Khan\nSoftware Engineer | Python Developer\nayesha@example.com\nEDUCATION\nBachelor of Science"
    assert analyzer.extract_resume_headline(text) == "Software Engineer | Python Developer"


def test_career_plan_omits_optional_certification_gap():
    plan = analyzer.build_career_plan({"section_reviews": {"certifications": {"present": False}}})
    assert not any("certification" in task["title"].casefold() for task in plan)


def test_job_match_lists_requirements_not_evidenced_in_resume():
    resume = "Python developer with machine learning and PyTorch projects."
    jd = "We need Python, PyTorch, XGBoost, LSTM, OpenCV, natural language processing, and data preprocessing."
    result = analyzer.deterministic_scores(resume, {}, jd)
    assert set(result["matching_skills"]) == {"python", "pytorch"}
    assert {"xgboost", "lstm", "opencv", "natural language processing", "data preprocessing"}.issubset(result["missing_skills"])


def test_rag_project_stack_is_recognized_as_job_requirements():
    brief = "Use Python and LangChain, Chroma or FAISS, embeddings, Streamlit, Hugging Face Spaces, chat history, citations, and RAGAS."
    result = analyzer.deterministic_scores("Python document question answering project", {}, brief)
    assert {"langchain", "chroma", "faiss", "embeddings", "streamlit", "hugging face spaces", "ragas"}.issubset(result["missing_skills"])
    assert "python" in result["matching_skills"]
