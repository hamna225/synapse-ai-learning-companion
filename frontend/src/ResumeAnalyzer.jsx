import { useEffect, useMemo, useState } from "react";
import "./resume-analyzer.css";

const API = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/+$/, "");
const OWNER = "synapse_student_id";
function ownerId() {
  let id = localStorage.getItem(OWNER);
  if (!id) { id = crypto.randomUUID(); localStorage.setItem(OWNER, id); }
  return id;
}
const nice = (value) => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const values = (x) => Array.isArray(x) ? x : [];

function Card({ title, children, className = "" }) {
  return <section className={`ci-card ${className}`}><h2>{title}</h2>{children}</section>;
}
function List({ items, emptyMessage = "Nothing identified in the resume text." }) {
  return values(items).length ? <ul className="ci-list">{items.map((item, index) => <li key={`${item}-${index}`}>{typeof item === "string" ? item : JSON.stringify(item)}</li>)}</ul> : <p className="ci-muted">{emptyMessage}</p>;
}
function Score({ title, value, breakdown, note }) {
  return <article className="ci-score"><span>{title}</span><strong>{Number.isFinite(value) ? <>{value}<small>/100</small></> : <small>Not calculated</small>}</strong>{note && <p>{note}</p>}{breakdown && <details><summary>Scoring breakdown</summary><ul>{Object.entries(breakdown).map(([name, row]) => <li key={name}><span>{name}</span><b>{row.earned == null ? "Not available" : `${row.earned}%`} · weight {row.weight}%</b></li>)}</ul></details>}</article>;
}

export default function ResumeAnalyzer({ page = "overview", setActivePage = () => {} }) {
  const [resume, setResume] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [jd, setJd] = useState("");
  const [role, setRole] = useState("");
  const [sourcePage, setSourcePage] = useState(1);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [builderSection, setBuilderSection] = useState("");
  const [builderResult, setBuilderResult] = useState("");
  const [builderTarget, setBuilderTarget] = useState("summary");

  async function loadHistory() {
    const r = await fetch(`${API}/resumes?owner=${encodeURIComponent(ownerId())}`);
    if (!r.ok) throw new Error("Could not load saved analyses.");
    const rows = await r.json(); setHistory(rows); return rows;
  }
  useEffect(() => {
    let active = true;
    fetch(`${API}/resumes?owner=${encodeURIComponent(ownerId())}`)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error("Could not load analyses")))
      .then((rows) => {
        if (!active) return;
        setHistory(rows);
        if (rows[0]) fetch(`${API}/resumes/${rows[0].id}?owner=${encodeURIComponent(ownerId())}`)
          .then((r) => r.ok ? r.json() : null).then((data) => { if (active && data) setResume(data); }).catch(() => {});
      }).catch(() => { if (active) setError("Could not connect to the resume service."); });
    return () => { active = false; };
  }, []);

  async function loadResume(id) {
    setError(""); setBusy(true);
    try {
      const r = await fetch(`${API}/resumes/${id}?owner=${encodeURIComponent(ownerId())}`);
      const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Could not open this analysis.");
      setResume(data); setJd(data.analysis.job_description || ""); setRole(data.analysis.target_role || ""); setActivePage("analyzer");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function upload(file) {
    if (!file) return;
    setError(""); setNotice(""); setBusy(true);
    try {
      const form = new FormData(); form.append("file", file); form.append("owner", ownerId());
      const r = await fetch(`${API}/resumes`, { method: "POST", body: form }); const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Resume upload failed.");
      setResume(data); setJd(""); setRole(""); setNotice("Resume analyzed and saved."); await loadHistory(); setActivePage("analyzer");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function post(path, payload = {}) {
    setBusy(true); setError("");
    try { const r = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload, owner: ownerId() }) }); const data = await r.json(); if (!r.ok) throw new Error(data.detail || "Request failed."); return data; }
    catch (e) { setError(e.message); return null; } finally { setBusy(false); }
  }
  async function runMatch() {
    if (!resume || jd.trim().length < 50) { setError("Paste a job description with at least 50 characters."); return; }
    const result = await post(`/resumes/${resume.id}/match`, { job_description: jd, target_role: role });
    if (result) { const next = { ...resume, analysis: { ...resume.analysis, job_description: jd, target_role: role, job_match: result } }; setResume(next); await loadHistory(); setNotice("Job comparison saved."); }
  }
  async function runBuilder() {
    if (builderSection.trim().length < 10) { setError("Paste at least 10 characters to improve."); return; }
    const result = await post(`/resumes/${resume.id}/improve`, { section: builderSection });
    if (result) setBuilderResult(result.improved_text);
  }
  async function remove(id) {
    if (!window.confirm("Delete this resume, its source file, and saved analysis?")) return;
    const r = await fetch(`${API}/resumes/${id}?owner=${encodeURIComponent(ownerId())}`, { method: "DELETE" });
    if (r.ok) { if (resume?.id === id) setResume(null); await loadHistory(); setNotice("Resume and analysis deleted."); } else setError("Could not delete this resume.");
  }

  const analysis = resume?.analysis;
  const match = analysis?.job_match;
  const stats = useMemo(() => ({ strengths: values(analysis?.strengths).length, actions: values(analysis?.suggestions).length }), [analysis]);
  const sourceUrl = resume ? `${API}/resumes/${resume.id}/source?owner=${encodeURIComponent(ownerId())}#page=${sourcePage}` : "";
  const openEvidence = (item) => { setSourcePage(item.page || 1); setSourceOpen(true); };
  const uploadControl = <label className="ci-button">{busy ? "Working…" : "Upload a resume"}<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" disabled={busy} onChange={(e) => upload(e.target.files?.[0])}/></label>;
  const formatList = (title, items) => <Card title={title}><List items={items}/></Card>;

  function render() {
    if (page === "overview") return <>
      <div className="ci-hero"><div><span>CAREER INTELLIGENCE</span><h1>Your career, made clearer.</h1><p>Grounded resume feedback, role matching, and practical next steps.</p></div>{uploadControl}</div>
      {!resume && !history.length ? <div className="ci-empty"><span className="material-symbols-outlined">description</span><h2>Start with your resume</h2><p>Upload a PDF or DOCX to get evidence based analysis. Scores appear only after a resume is processed.</p>{uploadControl}</div> : <>
        <div className="ci-score-grid"><Score title="Resume Quality" value={analysis?.quality_score}/><Score title="ATS Compatibility" value={analysis?.ats_score} note="Estimated compatibility, not an official ATS score."/><Score title="Job Match" value={match?.match_percentage}/><article className="ci-count"><span>Identified strengths</span><strong>{stats.strengths}</strong><small>Across saved analyses</small></article><article className="ci-count"><span>Improvement recommendations</span><strong>{stats.actions}</strong><small>Across saved analyses</small></article></div>
        <div className="ci-columns"><Card title="Top recommended actions">{analysis ? <List items={analysis.suggestions}/> : <p className="ci-muted">Open a saved analysis to review recommendations.</p>}</Card><Card title="Current resume"><strong>{resume?.filename || "No resume selected"}</strong><p className="ci-muted">{resume ? `${resume.text_length.toLocaleString()} readable characters` : "Choose a recent analysis to continue."}</p><button className="ci-link" onClick={() => setActivePage("history")}>View analysis history →</button></Card></div>
      </>}
      <Card title="Recent analysis history"><History rows={history.slice(0, 5)} open={loadResume} remove={remove}/></Card>
    </>;
    if (page === "matcher") return <>
      <h1>Job Matcher & Skill Gaps</h1><p className="ci-intro">Compare resume evidence with a target role, then review skills to develop, project ideas, and learning paths. Skills absent from the text are labeled “not evidenced,” not assumed absent.</p>
      {!resume ? <Card title="Choose a resume"><p>Upload a resume or reopen one from history to run a comparison.</p>{uploadControl}</Card> : <>
        <Card title="Target role and job description"><label className="ci-field">Target role<input value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. Data analyst"/></label><label className="ci-field">Job description<textarea rows="9" value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job description…"/></label><button className="ci-button" disabled={busy} onClick={runMatch}>Analyze match</button></Card>
        {match && <><div className="ci-score-grid"><Score title="Job Match" value={match.match_percentage} breakdown={match.score_breakdown}/></div><div className="ci-columns">{formatList("Skills evidenced in resume", match.matching_skills)}<Card title="Skills required by this job but not evidenced"><List items={match.missing_skills} emptyMessage="No recognized skill terms from this job description were identified as missing."/><p className="ci-muted">Not evidenced means the resume text does not show the skill; it does not establish that you lack it.</p></Card>{formatList("Required qualifications", match.required_qualifications)}{formatList("Relevant projects", match.relevant_projects)}{formatList("Recommended skills to develop", analysis.skill_development)}{formatList("Project ideas to build evidence", analysis.project_ideas)}{formatList("Suggested learning paths", analysis.learning_paths)}{formatList("Recommended resume changes", match.improvements)}</div></>}
      </>}
    </>;
    if (page === "ats") return <><h1>ATS Checker</h1><p className="ci-intro">A transparent estimate based on extracted text, headings, contact details, bullets, and readable content.</p>{!analysis ? <NeedsResume uploadControl={uploadControl}/> : <><div className="ci-score-grid"><Score title="ATS Compatibility" value={analysis.ats_score} breakdown={analysis.ats_breakdown} note={analysis.ats_disclaimer}/><Score title="Resume Quality" value={analysis.quality_score} breakdown={analysis.quality_breakdown}/></div>{formatList("Formatting and parsing warnings", analysis.formatting_warnings)}</>}</>;
    if (page === "builder") return <><h1>Resume Builder</h1><p className="ci-intro">Get a suggested rewrite. Your uploaded file is never silently overwritten.</p>{!resume ? <NeedsResume uploadControl={uploadControl}/> : <Card title="Improve a resume section"><label className="ci-field">Section to improve<select value={builderTarget} onChange={(e) => { const target = e.target.value; setBuilderTarget(target); const a = resume.analysis; const source = target === "summary" ? a.summary : target === "skills" ? values(a.technical_skills).join(", ") : target === "projects" ? values(a.projects).join("\n") : target === "experience" ? values(a.experience).map((x) => `${x.role || ""} ${x.organization || ""}\n${x.details || x.evidence || ""}`).join("\n\n") : target === "headline" ? a.resume_headline : ""; setBuilderSection(source || ""); setBuilderResult(""); }}><option value="summary">Professional summary</option><option value="skills">Technical skills</option><option value="projects">Project description</option><option value="experience">Work experience bullet</option><option value="headline">Resume headline</option></select></label><label className="ci-field">Original content<textarea rows="6" value={builderSection} onChange={(e) => setBuilderSection(e.target.value)} placeholder={builderTarget === "headline" ? "No headline was detected. You can paste the original headline here." : "Paste or edit the section content…"}/></label><button className="ci-button" disabled={busy} onClick={runBuilder}>Suggest a rewrite</button>{builderResult && <div className="ci-rewrite"><h3>Suggested content</h3><p>{builderResult}</p><p className="ci-muted">The rewrite improves clarity and action language while preserving your supplied facts. Review before use.</p><button className="ci-button secondary" onClick={() => navigator.clipboard.writeText(builderResult)}>Copy</button> <button className="ci-button secondary" onClick={() => setBuilderSection(builderResult)}>Use suggestion in draft</button><p className="ci-muted">Using this suggestion only updates the editor draft. Your uploaded file stays unchanged.</p></div>}</Card>}</>;
    if (page === "analyzer") return <><div className="ci-page-title"><div><h1>Resume Analyzer</h1><p className="ci-intro">Review extracted details, section gaps, and document evidence.</p></div>{uploadControl}</div>{!analysis ? <NeedsResume uploadControl={uploadControl}/> : <>
      <div className="ci-score-grid"><Score title="Resume Quality" value={analysis.quality_score} breakdown={analysis.quality_breakdown}/><Score title="ATS Compatibility" value={analysis.ats_score} breakdown={analysis.ats_breakdown} note={analysis.ats_disclaimer}/></div>
      <div className="ci-columns">{["contact", "summary", "education", "technical_skills", "experience", "projects", "certifications", "languages"].map((key) => { const review = analysis.section_reviews?.[key]; const content = key === "contact" ? Object.entries(analysis.contact_info || {}).flatMap(([type, entries]) => values(entries).map((entry) => `${nice(type)}: ${entry}`)) : key === "summary" ? [analysis.summary].filter(Boolean) : analysis[key]; return <Card key={key} title={nice(key)}><p className="ci-tag">{review?.present ? "Found in resume" : "Not found in resume text"}</p>{key === "experience" ? values(analysis.experience).map((item, i) => <button className="ci-evidence" key={i} onClick={() => openEvidence(item)}><b>{item.role || "Experience"} · {item.organization || "Organization not stated"}</b><span>{item.evidence} {item.page ? `(Page ${item.page})` : "(open source)"}</span></button>) : <List items={content}/>}<p className="ci-muted">{review?.good}</p><p className="ci-muted">{review?.missing_or_unclear}</p><p className="ci-muted">{review?.recommendation}</p></Card>; })}</div>
      <Card title="Source document"><p>{resume.filename} · {resume.size ? `${(resume.size / 1024).toFixed(0)} KB` : "Saved original"}</p><button className="ci-button secondary" onClick={() => setSourceOpen(!sourceOpen)}>{sourceOpen ? "Close original" : "Open original resume"}</button>{sourceOpen && <div className="ci-source">{resume.mime === "application/pdf" ? <iframe title="Original uploaded resume" src={sourceUrl}/> : <a href={sourceUrl}>Open preserved DOCX</a>}</div>}</Card>
      {analysis.missing_information?.length > 0 && formatList("Information not found in the document", analysis.missing_information)}
    </>}</>;
    if (page === "history") {
      return <>
        <h1>Analysis History</h1>
        <p className="ci-intro">Open a saved analysis to review its scores and recommendations.</p>
        <Card title="Saved analyses"><History rows={history} open={loadResume} remove={remove}/></Card>
      </>;
    }
    return <><h1>Settings</h1><Card title="Appearance"><p>Use the existing Synapse settings page for theme preferences.</p><button className="ci-button secondary" onClick={() => setActivePage("settings")}>Open application settings</button></Card></>;
  }

  return <main className="career-page">
    <header className="ci-topline"><div><span className="ci-eyebrow">SYNAPSE · CAREER INTELLIGENCE</span><div className="ci-breadcrumb">{nice(page)}</div></div>{history[0] && <button className="ci-resume-chip" onClick={() => loadResume(history[0].id)}>{resume?.filename || `Latest: ${history[0].filename}`}</button>}</header>
    {error && <div className="ci-alert" role="alert">{error}<button onClick={() => setError("")}>Dismiss</button></div>}{notice && <div className="ci-notice" role="status">{notice}</div>}
    {render()}
  </main>;
}

function NeedsResume({ uploadControl }) { return <div className="ci-empty"><span className="material-symbols-outlined">description</span><h2>Resume required</h2><p>Upload a resume or open a saved analysis to use this page.</p>{uploadControl}</div>; }
function History({ rows, open, remove }) {
  return rows.length ? <div className="ci-history">{rows.map((row) => <div className="ci-history-row" key={row.id}><button className="ci-history-open" onClick={() => open(row.id)}><b>{row.filename}</b><small>{new Date(row.created_at).toLocaleString()}</small></button><span>Quality {Number.isFinite(row.analysis?.quality_score) ? `${row.analysis.quality_score}/100` : "Not calculated"}</span><span>ATS {Number.isFinite(row.analysis?.ats_score) ? `${row.analysis.ats_score}/100` : "Not calculated"}</span>{row.analysis?.job_match && <span>Job {row.analysis.job_match.match_percentage}/100</span>}<button className="ci-delete" onClick={() => remove(row.id)}>Delete</button></div>)}</div> : <p className="ci-muted">No analyses saved yet.</p>;
}
