
import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./index.css";
import ResumeAnalyzer from "./ResumeAnalyzer.jsx";

/* =========================================================
   API
   ========================================================= */

const API_BASE = (
  import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

function getStudentProfileId() {
  let studentId = localStorage.getItem("synapse_student_id");
  if (!studentId) {
    studentId = globalThis.crypto?.randomUUID?.()
      || `student_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    localStorage.setItem("synapse_student_id", studentId);
  }
  return studentId;
}

/* =========================================================
   REUSABLE COMPONENTS
   ========================================================= */

function ProgressBar({ value, type = "primary" }) {
  return (
    <div className="progress-track">
      <div
        className={`progress-fill ${type}`}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  badge,
  footer,
  icon,
  iconType,
  progress,
  progressType,
}) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <div>
          <p className="eyebrow">{label}</p>

          <div className="stat-value-row">
            <span className="stat-value">{value}</span>

            {badge && (
              <span className="stat-badge">
                {badge}
              </span>
            )}
          </div>
        </div>

        <div className={`stat-icon ${iconType}`}>
          <span className="material-symbols-outlined">
            {icon}
          </span>
        </div>
      </div>

      <div className="stat-footer">
        {footer}
      </div>

      {progress !== undefined && (
        <ProgressBar
          value={progress}
          type={progressType}
        />
      )}
    </div>
  );
}

function MasteryItem({
  title,
  status,
  percentage,
  type,
  buttonText,
  onClick,
}) {
  return (
    <div className="mastery-item">
      <div className="mastery-header">
        <div className="mastery-title-wrap">
          <span className="mastery-title">
            {title}
          </span>

          <span className={`status ${type}`}>
            {status}
          </span>
        </div>

        <div className="mastery-actions">
          <span className={`mastery-score ${type}`}>
            {percentage}%
          </span>

          <button
            className={`small-button ${type === "error"
              ? "danger-button"
              : ""
              }`}
            onClick={onClick}
          >
            {buttonText}
          </button>
        </div>
      </div>

      <ProgressBar
        value={percentage}
        type={type}
      />
    </div>
  );
}

function ActivityItem({
  type,
  time,
  title,
  description,
  dot,
}) {
  return (
    <div className="activity-item">
      <div className={`activity-dot ${dot}`} />

      <div className="activity-content">
        <div className="activity-meta">
          <span>{type}</span>
          <small>{time}</small>
        </div>

        <h4>{title}</h4>

        <p>{description}</p>
      </div>
    </div>
  );
}

function LearningItem({
  icon,
  iconType,
  category,
  time,
  title,
  progress,
  progressText,
  buttonText,
  completed = false,
  onClick,
}) {
  return (
    <div
      className={`learning-item ${completed ? "completed-item" : ""
        }`}
    >
      <div className="learning-left">
        <div className={`material-icon ${iconType}`}>
          <span className="material-symbols-outlined">
            {icon}
          </span>
        </div>

        <div className="material-info">
          <div className="material-meta">
            <span>{category}</span>
            <span>• {time}</span>
          </div>

          <h4>{title}</h4>

          <div className="material-progress">
            <div className="material-progress-track">
              <div
                className={`material-progress-fill ${iconType}`}
                style={{
                  width: `${progress}%`,
                }}
              />
            </div>

            <span>{progressText}</span>
          </div>
        </div>
      </div>

      <button
        className="resume-button"
        onClick={onClick}
      >
        <span className="material-symbols-outlined">
          {completed ? "replay" : "play_arrow"}
        </span>

        {buttonText}
      </button>
    </div>
  );
}

/* =========================================================
   AI TUTOR
   ========================================================= */


/* =========================================================
   AI TUTOR WITH SAVED CONVERSATIONS
   ========================================================= */
const TUTOR_STORAGE_KEY = "synapse_conversations";
const TUTOR_ACTIVE_KEY = "synapse_active_conversation";

function TutorPage() {
  const starterMessage = {
    id: 1,
    role: "assistant",
    content:
      "Hi! Upload a PDF or reference document, then ask a question. I’ll answer from the document and link you to the source passages.",
  };

  /* -------------------------------------------------------
     LOAD SAVED CONVERSATIONS
     ------------------------------------------------------- */

  const [savedState] = useState(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem(TUTOR_STORAGE_KEY) || "[]"
      );

      const activeId = localStorage.getItem(
        TUTOR_ACTIVE_KEY
      );

      const activeConversation =
        saved.find(
          (conversation) =>
            conversation.id === activeId
        ) || saved[0];

      if (activeConversation) {
        return {
          conversations: saved,
          activeConversation,
        };
      }
    } catch (error) {
      console.error(
        "Could not load saved conversations:",
        error
      );
    }

    return {
      conversations: [],
      activeConversation: {
        id: `conversation_${Date.now()}`,
        title: "New Conversation",
        messages: [starterMessage],
        materialId:
          localStorage.getItem(
            "synapse_material_id"
          ) || "",
        materialName:
          localStorage.getItem(
            "synapse_material_name"
          ) || "",
        topics: [],
        sessionId: null,
      },
    };
  });

  const [
    conversations,
    setConversations,
  ] = useState(
    savedState.conversations || []
  );

  const [
    conversationId,
    setConversationId,
  ] = useState(
    savedState.activeConversation.id
  );

  const [
    messages,
    setMessages,
  ] = useState(
    savedState.activeConversation.messages ||
    [starterMessage]
  );

  const [input, setInput] = useState("");

  const [loading, setLoading] =
    useState(false);

  const [uploading, setUploading] =
    useState(false);

  const [uploadStatus, setUploadStatus] =
    useState("");

  const [topics, setTopics] = useState(() => {
    try {
      const conversationTopics =
        savedState.activeConversation.topics;

      if (
        Array.isArray(conversationTopics) &&
        conversationTopics.length > 0
      ) {
        return conversationTopics;
      }

      const materialTopics = JSON.parse(
        localStorage.getItem(
          "synapse_active_material_topics"
        ) || "[]"
      );

      return Array.isArray(materialTopics)
        ? materialTopics
        : [];
    } catch (error) {
      console.error(
        "Could not load saved material topics:",
        error
      );

      return [];
    }
  });


  const [topicsLoading, setTopicsLoading] =
    useState(false);
  const [topicsError, setTopicsError] = useState("");
  const [topicsAttemptedFor, setTopicsAttemptedFor] = useState("");

  const [backendOnline, setBackendOnline] =
    useState(false);

  const [sessionId, setSessionId] =
    useState(
      savedState.activeConversation
        .sessionId || null
    );

  const [materialId, setMaterialId] =
    useState(
      savedState.activeConversation
        .materialId ||
      localStorage.getItem(
        "synapse_material_id"
      ) ||
      ""
    );

  const [materialName, setMaterialName] =
    useState(
      savedState.activeConversation
        .materialName ||
      localStorage.getItem(
        "synapse_material_name"
      ) ||
      ""
    );

  const fileInputRef = useRef(null);

  const messagesEndRef = useRef(null);

  /* -------------------------------------------------------
     SAVE CONVERSATIONS TO LOCAL STORAGE
     ------------------------------------------------------- */

  useEffect(() => {
    try {
      localStorage.setItem(
        TUTOR_STORAGE_KEY,
        JSON.stringify(conversations)
      );
    } catch (error) {
      console.error(
        "Could not save conversations:",
        error
      );
    }
  }, [conversations]);

  /* -------------------------------------------------------
     CREATE CONVERSATION SNAPSHOT
     ------------------------------------------------------- */

  function createConversationSnapshot() {
    const firstUserMessage =
      messages.find(
        (message) =>
          message.role === "user"
      );

    const title =
      firstUserMessage?.content?.trim() ||
      materialName ||
      "New Conversation";

    return {
      id: conversationId,

      title:
        title.length > 50
          ? `${title.slice(0, 50)}...`
          : title,

      messages,

      materialId: materialId || "",

      materialName: materialName || "",

      topics: topics || [],

      sessionId: sessionId || null,

      updatedAt:
        new Date().toISOString(),
    };
  }

  /* -------------------------------------------------------
     UPSERT CONVERSATION
     ------------------------------------------------------- */

  function saveCurrentConversation() {
    const hasRealContent =
      messages.some(
        (message) =>
          message.role === "user"
      ) ||
      Boolean(materialId) ||
      topics.length > 0 ||
      messages.length > 1;

    if (!hasRealContent) {
      return;
    }

    const conversation =
      createConversationSnapshot();

    setConversations(
      (previous) => {
        const withoutCurrent =
          previous.filter(
            (item) =>
              item.id !==
              conversationId
          );

        return [
          conversation,
          ...withoutCurrent,
        ].slice(0, 20);
      }
    );
  }

  /* -------------------------------------------------------
     AUTO SAVE CURRENT CONVERSATION
     ------------------------------------------------------- */

  useEffect(() => {
    saveCurrentConversation();

    localStorage.setItem(
      TUTOR_ACTIVE_KEY,
      conversationId
    );
  }, [
    messages,
    materialId,
    materialName,
    topics,
    sessionId,
    conversationId,
  ]);

  /* -------------------------------------------------------
     CHECK BACKEND
     ------------------------------------------------------- */

  useEffect(() => {
    checkBackend();
  }, []);

  async function checkBackend() {
    try {
      const response = await fetch(
        `${API_BASE}/`
      );

      setBackendOnline(response.ok);
    } catch {
      setBackendOnline(false);
    }
  }

  /* -------------------------------------------------------
     AUTO SCROLL
     ------------------------------------------------------- */

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [
    messages,
    loading,
    topics,
  ]);

  /* -------------------------------------------------------
     CREATE SESSION
     ------------------------------------------------------- */

  async function createSession() {
    const response = await fetch(
      `${API_BASE}/sessions`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body: JSON.stringify({
          student_id: getStudentProfileId(),
        }),
      }
    );

    const data =
      await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
        "Could not create learning session."
      );
    }

    return data.session_id;
  }

  async function getOrCreateSession() {
    if (sessionId) {
      return sessionId;
    }

    const newSessionId =
      await createSession();

    setSessionId(newSessionId);

    return newSessionId;
  }

  /* -------------------------------------------------------
     FORMAT TIME
     ------------------------------------------------------- */

  function formatConversationTime(
    timestamp
  ) {
    if (!timestamp) {
      return "";
    }

    const date =
      new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  /* -------------------------------------------------------
     OPEN OLD CONVERSATION
     ------------------------------------------------------- */

  function openConversation(
    conversation
  ) {
    setConversationId(
      conversation.id
    );

    localStorage.setItem(
      TUTOR_ACTIVE_KEY,
      conversation.id
    );

    setMessages(
      conversation.messages ||
      [starterMessage]
    );

    setMaterialId(
      conversation.materialId || ""
    );

    setMaterialName(
      conversation.materialName ||
      ""
    );

    setTopics(
      conversation.topics || []
    );

    setSessionId(
      conversation.sessionId ||
      null
    );

    setUploadStatus("");

    setInput("");

    setLoading(false);

    setUploading(false);

    if (conversation.materialId) {
      localStorage.setItem(
        "synapse_material_id",
        conversation.materialId
      );

      localStorage.setItem(
        "synapse_material_name",
        conversation.materialName ||
        ""
      );
    } else {
      localStorage.removeItem(
        "synapse_material_id"
      );

      localStorage.removeItem(
        "synapse_material_name"
      );
    }
  }

  /* -------------------------------------------------------
     NEW CONVERSATION
     ------------------------------------------------------- */

  function newConversation() {
    saveCurrentConversation();

    const newId =
      `conversation_${Date.now()}`;

    setConversationId(newId);

    setMessages([
      {
        id: Date.now(),
        role: "assistant",
        content:
          "Hi! Upload a PDF or reference document, then ask a question. I’ll answer from the document and link you to the source passages.",
      },
    ]);

    setInput("");

    setTopics([]);

    setUploadStatus("");

    setMaterialId("");

    setMaterialName("");

    setSessionId(null);

    setLoading(false);

    setUploading(false);

    localStorage.setItem(
      TUTOR_ACTIVE_KEY,
      newId
    );

    localStorage.removeItem(
      "synapse_material_id"
    );

    localStorage.removeItem(
      "synapse_material_name"
    );
  }

  /* -------------------------------------------------------
     DELETE CONVERSATION
     ------------------------------------------------------- */

  function deleteConversation(
    conversationIdToDelete
  ) {
    const isCurrent =
      conversationIdToDelete ===
      conversationId;

    const remaining =
      conversations.filter(
        (conversation) =>
          conversation.id !==
          conversationIdToDelete
      );

    setConversations(
      remaining
    );

    if (!isCurrent) {
      return;
    }

    const newId =
      `conversation_${Date.now()}`;

    setConversationId(newId);

    setMessages([
      {
        id: Date.now(),
        role: "assistant",
        content:
      "Hi! Upload a PDF or reference document, then ask a question. I’ll answer from the document and link you to the source passages.",
      },
    ]);

    setTopics([]);

    setInput("");

    setMaterialId("");

    setMaterialName("");

    setSessionId(null);

    setUploadStatus("");

    localStorage.setItem(
      TUTOR_ACTIVE_KEY,
      newId
    );

    localStorage.removeItem(
      "synapse_material_id"
    );

    localStorage.removeItem(
      "synapse_material_name"
    );
  }

  /* -------------------------------------------------------
     NORMALIZE TOPICS
     ------------------------------------------------------- */

  function normalizeTopic(
    topic,
    index
  ) {
    /*
     * Supports:
     *
     * "Arrays"
     *
     * {
     *   topic: "Data Structures",
     *   subtopics: ["Arrays", "Linked Lists"]
     * }
     *
     * {
     *   name: "Arrays",
     *   subtopics: [...]
     * }
     */

    if (typeof topic === "string") {
      return {
        id: `${topic}-${index}`,
        name: topic,
        subtopics: [],
      };
    }

    if (
      topic &&
      typeof topic === "object"
    ) {
      return {
        id:
          topic.id ||
          `${topic.topic || topic.name || "topic"}-${index}`,

        name:
          topic.topic ||
          topic.name ||
          topic.title ||
          "Untitled Topic",

        subtopics:
          Array.isArray(
            topic.subtopics
          )
            ? topic.subtopics
            : [],
      };
    }

    return {
      id: `topic-${index}`,
      name: "Untitled Topic",
      subtopics: [],
    };
  }

  /* -------------------------------------------------------
     LOAD TOPICS
     ------------------------------------------------------- */

  async function loadTopics(
    newMaterialId
  ) {
    try {
      setTopicsAttemptedFor(newMaterialId);
      setTopicsError("");
      setTopicsLoading(true);

      const response =
        await fetch(
          `${API_BASE}/topics`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify({
              material_id:
                newMaterialId,
            }),
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
          "Could not load topics."
        );
      }

      console.log(
        "Topics received from backend:",
        data.topics
      );

      setTopics(
        Array.isArray(data.topics)
          ? data.topics
          : []
      );

    } catch (error) {

      console.error(
        "Topic loading error:",
        error
      );

      setTopics([]);
      setTopicsError(error?.message || "Topic discovery failed.");

    } finally {

      setTopicsLoading(false);
    }
  }

  useEffect(() => {
    if (materialId && topicsAttemptedFor !== materialId && !topicsLoading) {
      loadTopics(materialId);
    }
  }, [materialId, topicsAttemptedFor, topicsLoading]);

  /* -------------------------------------------------------
     YOUTUBE UPLOAD
     ------------------------------------------------------- */

  async function handleYouTubeUpload(
    youtubeUrl
  ) {
    if (!youtubeUrl.trim()) {
      return;
    }

    try {
      saveCurrentConversation();

      const newConversationId =
        `conversation_${Date.now()}`;

      setConversationId(
        newConversationId
      );

      setMessages([
        {
          id: Date.now(),
          role: "assistant",
          content:
            "I'm processing the YouTube video. Please wait...",
        },
      ]);

      setTopics([]);

      setMaterialId("");

      setMaterialName("");

      setSessionId(null);

      setUploadStatus(
        "Processing YouTube video..."
      );

      setUploading(true);

      localStorage.setItem(
        TUTOR_ACTIVE_KEY,
        newConversationId
      );

      localStorage.removeItem(
        "synapse_material_id"
      );

      localStorage.removeItem(
        "synapse_material_name"
      );

      /* Create session */

      const currentSessionId =
        await createSession();

      setSessionId(
        currentSessionId
      );

      /* Prepare YouTube URL */

      const formData =
        new FormData();

      formData.append(
        "youtube_url",
        youtubeUrl.trim()
      );

      setUploadStatus(
        "Reading YouTube transcript..."
      );

      /* Upload YouTube */

      const response =
        await fetch(
          `${API_BASE}/sessions/${currentSessionId}/youtube`,
          {
            method: "POST",
            body: formData,
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
          "YouTube processing failed."
        );
      }

      console.log(
        "YouTube upload result:",
        data
      );

      /* Save material */

      setMaterialId(
        data.material_id
      );

      setMaterialName(
        "YouTube Video"
      );

      localStorage.setItem(
        "synapse_material_id",
        data.material_id
      );

      localStorage.setItem(
        "synapse_material_name",
        "YouTube Video"
      );

      setUploadStatus(
        `${data.chunks} chunks are ready.`
      );

      setMessages(
        (previous) => [
          ...previous,
          {
            id: Date.now(),
            role: "system",
            content:
              `YouTube video is ready. ${data.chunks} transcript chunks have been indexed.`,
          },
        ]
      );

      /* Analyze topics */

      setUploadStatus(
        "Finding topics covered in the video..."
      );

      await loadTopics(
        data.material_id
      );

      setUploadStatus(
        "YouTube video connected. You can start learning."
      );

    } catch (error) {

      console.error(
        "YouTube upload error:",
        error
      );

      setUploadStatus(
        `YouTube processing failed: ${error.message}`
      );

      setMessages(
        (previous) => [
          ...previous,
          {
            id: Date.now(),
            role: "system",
            content:
              `YouTube processing failed: ${error.message}`,
          },
        ]
      );

    } finally {

      setUploading(false);
    }
  }

  /* -------------------------------------------------------
     UPLOAD PDF / PPT / PPTX
     ------------------------------------------------------- */

  async function handleUpload(
    event
  ) {
    const file =
      event.target.files?.[0];

    if (!file) {
      return;
    }

    const extension =
      "." +
      file.name
        .split(".")
        .pop()
        .toLowerCase();

    const allowed = [
      ".pdf",
      ".ppt",
      ".pptx",
    ];

    if (
      !allowed.includes(
        extension
      )
    ) {
      alert(
        "Please upload a PDF, PPT, or PPTX file."
      );

      event.target.value = "";

      return;
    }

    try {
      saveCurrentConversation();

      const newConversationId =
        `conversation_${Date.now()}`;

      setConversationId(
        newConversationId
      );

      setMessages([
        {
          id: Date.now(),
          role: "assistant",
          content:
            "I'm studying your new learning material. Please wait until processing is complete.",
        },
      ]);

      setTopics([]);

      setMaterialId("");

      setMaterialName("");

      setSessionId(null);

      setUploadStatus(
        "Uploading your lecture..."
      );

      setUploading(true);

      localStorage.setItem(
        TUTOR_ACTIVE_KEY,
        newConversationId
      );

      localStorage.removeItem(
        "synapse_material_id"
      );

      localStorage.removeItem(
        "synapse_material_name"
      );

      /* Create NEW session */

      const currentSessionId =
        await createSession();

      setSessionId(
        currentSessionId
      );

      /* Prepare file */

      const formData =
        new FormData();

      formData.append(
        "file",
        file
      );

      setUploadStatus(
        "Extracting and indexing text. Figure analysis follows in the background; the first upload may take longer while local embeddings initialize..."
      );

      /* Upload */

      const response =
        await fetch(
          `${API_BASE}/sessions/${currentSessionId}/materials`,
          {
            method: "POST",
            body: formData,
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
          "Upload failed."
        );
      }

      setMaterialId(
        data.material_id
      );

      setMaterialName(
        data.filename
      );

      localStorage.setItem(
        "synapse_material_id",
        data.material_id
      );

      localStorage.setItem(
        "synapse_material_name",
        data.filename
      );

      setUploadStatus(
        data.visual_analysis_pending
          ? `${data.chunks} text chunks are ready. Figure analysis continues in the background.`
          : `${data.chunks} chunks are ready.`
      );

      setMessages(
        (previous) => [
          ...previous,
          {
            id: Date.now(),
            role: "system",
            content:
              data.visual_analysis_pending
                ? `${data.filename} is ready for text-based study. Figure analysis continues in the background.`
                : `${data.filename} is ready. ${data.chunks} chunks have been indexed.`,
          },
        ]
      );

      /* Analyze topics */

      setUploadStatus(
        "Text is indexed. Finding topics; figure analysis continues in the background..."
      );

      // Text is already searchable; do not block tutoring while topic discovery runs.
      setUploading(false);

      await loadTopics(
        data.material_id
      );

      setUploadStatus(
        data.visual_analysis_pending
          ? "Your material is ready for text-based study. Figure descriptions are processed separately."
          : "Your material is ready. You can start learning."
      );

    } catch (error) {

      console.error(
        "Upload error:",
        error
      );

      setUploadStatus(
        `Upload failed: ${error.message}`
      );

      setMessages(
        (previous) => [
          ...previous,
          {
            id: Date.now(),
            role: "system",
            content:
              `Upload failed: ${error.message}`,
          },
        ]
      );

    } finally {

      setUploading(false);

      event.target.value = "";
    }
  }

  /* -------------------------------------------------------
     ASK QUESTION
     ------------------------------------------------------- */

  async function askQuestion(
    questionText = input
  ) {
    if (uploading || loading) {
      return;
    }

    const question =
      questionText.trim();

    if (!question) {
      return;
    }

    setInput("");

    setMessages(
      (previous) => [
        ...previous,
        {
          id: Date.now(),
          role: "user",
          content: question,
        },
      ]
    );

    try {
      setLoading(true);

      /* =====================================================
         YOUTUBE URL DETECTION
         ===================================================== */

      const youtubeRegex =
        /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)/;

      if (
        youtubeRegex.test(
          question
        )
      ) {

        let currentSessionId =
          sessionId;

        if (!currentSessionId) {
          currentSessionId =
            await createSession();

          setSessionId(
            currentSessionId
          );
        }

        setUploadStatus(
          "Processing YouTube video..."
        );

        setUploading(true);

        const formData =
          new FormData();

        formData.append(
          "youtube_url",
          question
        );

        const response =
          await fetch(
            `${API_BASE}/sessions/${currentSessionId}/youtube`,
            {
              method: "POST",
              body: formData,
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data?.detail ||
            "YouTube processing failed."
          );
        }

        console.log(
          "YouTube upload result:",
          data
        );

        setMaterialId(
          data.material_id
        );

        setMaterialName(
          "YouTube Video"
        );

        localStorage.setItem(
          "synapse_material_id",
          data.material_id
        );

        localStorage.setItem(
          "synapse_material_name",
          "YouTube Video"
        );

        setUploadStatus(
          "Video processed. Finding topics..."
        );

        await loadTopics(
          data.material_id
        );

        setUploadStatus(
          "YouTube video connected."
        );

        setMessages(
          (previous) => [
            ...previous,
            {
              id:
                Date.now() + 1,
              role: "system",
              content:
                "🎥 YouTube video connected successfully. I can now answer questions using this video.",
            },
          ]
        );

        return;
      }

      /* =====================================================
         NORMAL AI / RAG QUESTION
         ===================================================== */

      const response =
        await fetch(
          `${API_BASE}/ask`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify({
              material_id:
                materialId || null,

              question:
                question,
            }),
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
          "Tutor request failed."
        );
      }

      setMessages(
        (previous) => [
          ...previous,
          {
            id:
              Date.now() + 1,
            role: "assistant",
            content:
              data.answer ||
              "I could not generate an answer.",
            sources:
              (data.sources || [])
                .filter((source) =>
                  (data.answer || "").includes(`[${source.number}]`)
                )
                .map((source) => ({
                ...source,
                url: source.url.startsWith("http")
                  ? source.url
                  : `${API_BASE}${source.url}`,
                })),
          },
        ]
      );

    } catch (error) {

      console.error(
        "Tutor error:",
        error
      );

      setMessages(
        (previous) => [
          ...previous,
          {
            id:
              Date.now() + 2,
            role: "assistant",
            content:
              `I couldn't process that right now.\n\n${error.message}`,
            error: true,
          },
        ]
      );

    } finally {

      setLoading(false);
      setUploading(false);
    }
  }

  /* -------------------------------------------------------
     BOLD TEXT
     ------------------------------------------------------- */

  function formatBoldText(text) {
    const parts =
      text.split(
        /(\*\*.*?\*\*)/g
      );

    return parts.map(
      (part, index) => {

        if (
          part.startsWith("**") &&
          part.endsWith("**")
        ) {
          return (
            <strong key={index}>
              {part.slice(2, -2)}
            </strong>
          );
        }

        return (
          <span key={index}>
            {part}
          </span>
        );
      }
    );
  }

  /* -------------------------------------------------------
     ANSWER FORMATTER
     ------------------------------------------------------- */

  function normalizeTutorMath(value) {
    return String(value || "")
      // Remove LaTeX display and inline math delimiters
      .replace(/\\{1,2}\[([\s\S]*?)\\{1,2}\]/g, "$1")
      .replace(/\\{1,2}\(([\s\S]*?)\\{1,2}\)/g, "$1")

      // Convert common LaTeX commands into readable symbols
      .replace(/\\text\{([^{}]*)\}/g, "$1")
      .replace(/\\mathrm\{([^{}]*)\}/g, "$1")
      .replace(/\\operatorname\{([^{}]*)\}/g, "$1")
      .replace(/\\operatorname\s+/g, "")
      .replace(/\\lambda\b/g, "λ")
      .replace(/\\Sigma\b/g, "Σ")
      .replace(/\\in\b/g, "∈")
      .replace(/\\mid\b/g, "|")
      .replace(/\\star\b/g, "*")
      .replace(/\\neq\b/g, "≠")
      .replace(/\\leq\b/g, "≤")
      .replace(/\\geq\b/g, "≥")
      .replace(/\\rightarrow\b/g, "→")
      .replace(/\\times\b/g, "×")
      .replace(/\\,|\\;|\\:/g, " ")
      .replace(/\\left\b|\\right\b/g, "")
      .replace(/\\ /g, " ")
      .replace(/[{}]/g, "")
      .trim();
  }

  function renderAnswer(text) {
    const readableText = normalizeTutorMath(text);
    const lines = readableText.split("\n");

    return (
      <div className="tutor-answer-text">

        {lines.map(
          (line, index) => {

            const trimmed =
              line.trim();

            if (!trimmed) {
              return (
                <div
                  key={index}
                  className="answer-space"
                />
              );
            }

            if (
              /^[-_*]{3,}$/.test(
                trimmed
              )
            ) {
              return null;
            }

            if (
              /^\|?[\s:|-]+\|[\s:|-]*\|?$/.test(
                trimmed
              )
            ) {
              return null;
            }

            if (
              trimmed.startsWith("|")
            ) {
              return (
                <p key={index}>
                  {formatBoldText(
                    trimmed
                      .replace(
                        /^\|/,
                        ""
                      )
                      .replace(
                        /\|$/,
                        ""
                      )
                      .replace(
                        /\|/g,
                        " "
                      )
                      .trim()
                  )}
                </p>
              );
            }

            if (
              trimmed.startsWith(
                "# "
              )
            ) {
              return (
                <h3
                  key={index}
                  className="answer-heading"
                >
                  {formatBoldText(
                    trimmed.slice(2)
                  )}
                </h3>
              );
            }

            if (
              trimmed.startsWith(
                "## "
              )
            ) {
              return (
                <h3
                  key={index}
                  className="answer-heading"
                >
                  {formatBoldText(
                    trimmed.slice(3)
                  )}
                </h3>
              );
            }

            if (
              trimmed.startsWith(
                "### "
              )
            ) {
              return (
                <h4
                  key={index}
                  className="answer-heading-small"
                >
                  {formatBoldText(
                    trimmed.slice(4)
                  )}
                </h4>
              );
            }

            const boldHeading =
              trimmed.match(
                /^\*\*(.+?)\*\*$/
              );

            if (boldHeading) {
              return (
                <h3
                  key={index}
                  className="answer-heading"
                >
                  {boldHeading[1]}
                </h3>
              );
            }

            if (
              trimmed.startsWith(
                "> "
              )
            ) {
              return (
                <div
                  key={index}
                  className="answer-example"
                >
                  {formatBoldText(
                    trimmed.slice(2)
                  )}
                </div>
              );
            }

            if (
              trimmed.startsWith(
                "- "
              ) ||
              trimmed.startsWith(
                "* "
              )
            ) {
              return (
                <div
                  key={index}
                  className="answer-bullet"
                >

                  <span className="bullet-mark">
                    •
                  </span>

                  <span>
                    {formatBoldText(
                      trimmed.slice(2)
                    )}
                  </span>

                </div>
              );
            }

            const numberMatch =
              trimmed.match(
                /^(\d+)\.\s+(.*)$/
              );

            if (numberMatch) {
              return (
                <div
                  key={index}
                  className="answer-number"
                >

                  <span className="number-mark">
                    {numberMatch[1]}.
                  </span>

                  <span>
                    {formatBoldText(
                      numberMatch[2]
                    )}
                  </span>

                </div>
              );
            }

            return (
              <p key={index}>
                {formatBoldText(
                  trimmed
                )}
              </p>
            );
          }
        )}

      </div>
    );
  }

  /* =======================================================
     TUTOR UI
     ======================================================= */

  return (
    <div className="tutor-page">

      <div className="tutor-layout">

        {/* =================================================
            SIDEBAR
            ================================================= */}

        <aside className="tutor-sidebar">

          <div className="tutor-sidebar-top">

            <div className="tutor-product-name">
              Synapse
            </div>

            <div className="tutor-product-subtitle">
              Personal AI Learning Assistant
            </div>

          </div>

          {/* NEW CHAT */}

          <button
            className="tutor-new-chat"
            onClick={
              newConversation
            }
          >
            ＋ New Conversation
          </button>

          {/* SAVED CONVERSATIONS */}

          <div className="tutor-sidebar-heading">
            Recent Conversations
          </div>

          <div className="tutor-conversation-list">

            {conversations.length ===
              0 ? (

              <div className="tutor-empty-history">
                Your previous conversations
                will appear here.
              </div>

            ) : (

              conversations
                .slice(0, 20)
                .map(
                  (
                    conversation
                  ) => (

                    <div
                      key={
                        conversation.id
                      }
                      className={`tutor-conversation-item ${conversation.id ===
                          conversationId
                          ? "current"
                          : ""
                        }`}
                    >

                      <button
                        className="tutor-conversation-open"
                        onClick={() =>
                          openConversation(
                            conversation
                          )
                        }
                      >

                        <div className="tutor-chat-icon">

                          <span className="material-symbols-outlined">
                            chat
                          </span>

                        </div>

                        <div className="tutor-conversation-text">

                          <span className="tutor-conversation-title">
                            {
                              conversation.title
                            }
                          </span>

                          <span className="tutor-conversation-time">
                            {formatConversationTime(
                              conversation.updatedAt
                            )}
                          </span>

                        </div>

                      </button>

                      <button
                        className="tutor-delete-conversation"
                        onClick={(
                          event
                        ) => {

                          event.stopPropagation();

                          deleteConversation(
                            conversation.id
                          );

                        }}
                        title="Delete conversation"
                      >
                        ×
                      </button>

                    </div>

                  )
                )

            )}

          </div>

          {/* MATERIAL */}

          <div className="tutor-sidebar-heading">
            Learning Material
          </div>

          <div className="tutor-sidebar-material">

            {materialName ? (

              <>

                <div className="sidebar-material-icon">
                  📚
                </div>

                <div>

                  <strong>
                    {materialName}
                  </strong>

                  <span>
                    Ready for learning
                  </span>

                </div>

              </>

            ) : (

              <div className="sidebar-no-material">
                Upload a PDF or reference document to begin.
              </div>

            )}

          </div>

          <div className="tutor-sidebar-bottom">

            <div className="tutor-grounded-card">

              <div className="tutor-grounded-icon">
                ✦
              </div>

              <div>

                <strong>
                  Document-grounded assistant
                </strong>

                <span>
                  Ask questions and open source citations from your uploaded files.
                </span>

              </div>

            </div>

          </div>

        </aside>

        {/* =================================================
            MAIN
            ================================================= */}

        <main className="tutor-main">

          {/* HEADER */}

          <header className="tutor-header">

            <div className="tutor-header-left">

              <div className="tutor-ai-avatar">
                ✦
              </div>

              <div>

                  <h1>
                    Document Q&amp;A
                  </h1>

                <div className="tutor-header-meta">

                  <span>
                    Answers grounded in your documents
                  </span>

                  <span>
                    •
                  </span>

                  <span
                    className={
                      backendOnline
                        ? "tutor-status online"
                        : "tutor-status offline"
                    }
                  >

                    <span className="tutor-status-dot" />

                    {backendOnline
                      ? "Backend connected"
                      : "Backend offline"}

                  </span>

                </div>

              </div>

            </div>

            {materialName && (

              <div className="tutor-material-badge">

                📚

                <span>
                  {materialName}
                </span>

              </div>

            )}

          </header>

          {/* =================================================
              UPLOAD STATUS
              ================================================= */}

          {uploadStatus && (

            <div
              className={`tutor-upload-status ${uploading
                  ? "processing"
                  : "ready"
                }`}
            >

              <div className="tutor-upload-status-icon">

                {uploading ? (

                  <span className="upload-spinner" />

                ) : (

                  "✓"

                )}

              </div>

              <div className="tutor-upload-status-content">

                <strong>

                  {uploading
                    ? "Studying your material"
                    : "Learning material ready"}

                </strong>

                <span>
                  {uploadStatus}
                </span>

              </div>

            </div>

          )}

          {/* =================================================
              CHAT
              ================================================= */}

          <section className="tutor-chat-area">

            {/* =================================================
                LEARNING MAP — FIRST
                ================================================= */}

            {materialId && (

                <div className="topics-panel">

                  <div className="topics-panel-header">

                    <div>

                      <span className="topics-label">
                        LEARNING MAP
                      </span>

                      <strong>
                        Topics in this document
                      </strong>

                      <span>
                        Main concepts identified
                        from your uploaded material
                      </span>

                    </div>

                    {topicsLoading && (

                      <span className="topics-loading">
                        Analyzing material...
                      </span>

                    )}

                  </div>

                  {/* TOPIC LOADING */}

                  {topicsLoading ? (

                    <div className="topics-skeleton">

                      <span />
                      <span />
                      <span />
                      <span />
                      <span />

                    </div>

                  ) : topics.length > 0 ? (
<div className="topic-list">
  {topics.map((topic, index) => {
    const normalized = normalizeTopic(topic, index);

    return (
      <div
        key={normalized.id || index}
        className="topic-chip"
      >
        <span className="topic-number">
          {index + 1}
        </span>

        <div className="topic-content">
          <span className="topic-name">
            {normalized.name}
          </span>
        </div>
      </div>
    );
  })}
</div>
                  ) : (
                    <div className="topics-empty-state">
                      <span>{topicsError || "No topics were identified in this document yet."}</span>
                      <button type="button" onClick={() => loadTopics(materialId)} disabled={topicsLoading}>Try topic detection again</button>
                    </div>
                  )}

                </div>

              )}

            {/* =================================================
                WELCOME — SECOND
                ================================================= */}

            {!messages.some(
              (message) =>
                message.role ===
                "user"
            ) && (

                <div className="tutor-welcome">

                  <span className="tutor-welcome-badge">
                    ADAPTIVE AI
                  </span>

                  <h2>
                    Learn from your own material.
                  </h2>

                  <p>
                    Upload lectures, textbooks,
                    slides or notes. Synapse will
                    study the material and help you
                    understand difficult concepts
                    in a simple way.
                  </p>

                </div>

              )}

            {/* =================================================
                MESSAGES — THIRD
                ================================================= */}

            <div className="tutor-messages">

              {messages.map(
                (message) => {

                  /* SYSTEM */

                  if (
                    message.role ===
                    "system"
                  ) {

                    return (

                      <div
                        key={
                          message.id
                        }
                        className="tutor-system-message"
                      >
                        ✓{" "}
                        {message.content}
                      </div>

                    );

                  }

                  /* USER */

                  if (
                    message.role ===
                    "user"
                  ) {

                    return (

                      <div
                        key={
                          message.id
                        }
                        className="tutor-message-row user"
                      >

                        <div className="tutor-user-bubble">
                          {message.content}
                        </div>

                      </div>

                    );

                  }

                  /* AI */

                  return (

                    <div
                      key={
                        message.id
                      }
                      className="tutor-message-row assistant"
                    >

                      <div className="tutor-message-avatar">
                        ✦
                      </div>

                      <div className="tutor-assistant-column">

                        <div
                          className={`tutor-assistant-bubble ${message.error
                              ? "error"
                              : ""
                            }`}
                        >

                          <div className="tutor-ai-label">
                            Chat with Documents
                          </div>

                          {renderAnswer(
                            message.content
                          )}

                          {message.sources?.length > 0 && (
                            <div className="tutor-answer-sources">
                              <strong>Cited course material</strong>
                              {message.sources.map((source) => (
                                <div key={`${source.url}-${source.number}`}>
                                  <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    [{source.number}] {source.label}
                                  </a>
                                </div>
                              ))}
                            </div>
                          )}

                        </div>

                      </div>

                    </div>

                  );

                }
              )}

              {/* LOADING */}

              {loading && (

                <div className="tutor-message-row assistant">

                  <div className="tutor-message-avatar">
                    ✦
                  </div>

                  <div className="tutor-loading-bubble">

                    <div className="loading-dots">

                      <span />
                      <span />
                      <span />

                    </div>

                    <label>
                      Thinking from your material...
                    </label>

                  </div>

                </div>

              )}

              <div
                ref={
                  messagesEndRef
                }
              />

            </div>

          </section>

          {/* =================================================
              COMPOSER
              ================================================= */}

          <footer className="tutor-composer-section">

            <div className="tutor-composer">

              <button
                className="tutor-attach-button"
                onClick={() =>
                  fileInputRef.current?.click()
                }
                disabled={
                  uploading
                }
                title="Upload a document"
              >
                📎
              </button>

              <input
                ref={
                  fileInputRef
                }
                type="file"
                accept=".pdf,.ppt,.pptx"
                hidden
                onChange={
                  handleUpload
                }
              />

              <div className="tutor-input-wrapper">

                <textarea
                  value={input}
                  onChange={(event) =>
                    setInput(
                      event.target.value
                    )
                  }
                  onKeyDown={(event) => {

                    if (
                      event.key ===
                      "Enter" &&
                      !event.shiftKey
                    ) {

                      event.preventDefault();

                      askQuestion();

                    }

                  }}
                  placeholder={
                    uploading
                      ? "Studying your material..."
                      : materialId
                        ? "Ask a question about your uploaded document..."
                        : "Ask me anything..."
                  }
                  rows={1}
                  disabled={
                    loading ||
                    uploading
                  }
                />

                <span className="tutor-input-hint">
                  Enter to send · Shift + Enter for new line
                </span>

              </div>

              <button
                className="tutor-send-button"
                onClick={() =>
                  askQuestion()
                }
                disabled={
                  loading ||
                  uploading ||
                  !input.trim()
                }
              >
                ↑
              </button>

            </div>

            <div className="tutor-composer-footer">

              <span>

                {uploading
                  ? "Processing lecture..."
                  : materialId
                    ? "Material connected"
                    : "No material connected"}

              </span>

              <span>
                Synapse Document Q&amp;A
              </span>

            </div>

          </footer>

        </main>

      </div>

    </div>
  );
}

/* =========================================================
   LEARNING MATERIALS
   ========================================================= */

function normalizeTopic(item) {
  if (typeof item === "string") {
    return {
      topic: item,
      subtopics: [],
    };
  }

  if (item && typeof item === "object") {
    return {
      topic:
        typeof item.topic === "string"
          ? item.topic
          : typeof item.name === "string"
            ? item.name
            : "Untitled Topic",

      subtopics: Array.isArray(item.subtopics)
        ? item.subtopics.map((sub) =>
          typeof sub === "string"
            ? sub
            : sub?.name || sub?.topic || ""
        )
        : [],
    };
  }

  return {
    topic: "",
    subtopics: [],
  };
}


/* =========================================================
   LEARNING MATERIALS
   ========================================================= */
function MaterialsPage({ setActivePage, onTakeQuiz }) {
  const [materials, setMaterials] = useState([]);

  const [showPractice, setShowPractice] =
    useState(false);

  const [selectedMaterial, setSelectedMaterial] =
    useState(null);

  const [questionCount, setQuestionCount] =
    useState(20);

  const [difficulty, setDifficulty] =
    useState("Medium");

  const [generating, setGenerating] =
    useState(false);

  const [generatedQuestions, setGeneratedQuestions] =
    useState([]);

  const [generationError, setGenerationError] =
    useState("");


  /* =========================================================
     LOAD MATERIALS
     ========================================================= */

  useEffect(() => {
    loadMaterials();
  }, []);


  function loadMaterials() {
    try {
      const conversations = JSON.parse(
        localStorage.getItem(
          "synapse_conversations"
        ) || "[]"
      );

      const materialMap = new Map();

      conversations.forEach(
        (conversation) => {

          if (!conversation.materialId) {
            return;
          }

          const material = {
            materialId:
              conversation.materialId,

            materialName:
              conversation.materialName ||
              "Learning Material",

            topics:
              Array.isArray(
                conversation.topics
              )
                ? conversation.topics
                : [],

            updatedAt:
              conversation.updatedAt ||
              null,

            sessionId:
              conversation.sessionId ||
              null,
          };


          const existing =
            materialMap.get(
              material.materialId
            );


          if (
            !existing ||
            new Date(
              material.updatedAt || 0
            ) >
            new Date(
              existing.updatedAt || 0
            )
          ) {
            materialMap.set(
              material.materialId,
              material
            );
          }

        }
      );


      setMaterials(
        Array.from(
          materialMap.values()
        ).sort(
          (a, b) =>
            new Date(
              b.updatedAt || 0
            ) -
            new Date(
              a.updatedAt || 0
            )
        )
      );

    } catch (error) {

      console.error(
        "Could not load materials:",
        error
      );

      setMaterials([]);

    }
  }


  /* =========================================================
     OPEN SUBJECTIVE PRACTICE
     ========================================================= */

  function openSubjectivePractice(
    material
  ) {

    setSelectedMaterial(material);

    setGeneratedQuestions([]);

    setGenerationError("");

    setQuestionCount(20);

    setDifficulty("Medium");

    setShowPractice(true);
  }


  /* =========================================================
     OPEN ADAPTIVE QUIZ
     ========================================================= */
  function openAdaptiveQuiz(material) {
    // Reset analytics for the new quiz
    // Keep your existing quiz-starting code below
    // ...
  }
  function openAdaptiveQuiz(material) {

    /*
      The student never needs to see or type
      the material ID.

      The actual material object already contains:
      material.materialId
      material.materialName
      material.topics
    */

    if (!material?.materialId) {

      console.error(
        "Cannot start quiz: material ID is missing.",
        material
      );

      alert(
        "This material does not have a valid ID. Please upload the material again."
      );

      return;
    }


    /*
      Save selected material as well.
      This makes the selected material available
      if the user refreshes or returns to the tutor.
    */

    localStorage.setItem(
      "synapse_quiz_material_id",
      material.materialId
    );

    localStorage.setItem(
      "synapse_quiz_material_name",
      material.materialName
    );

    localStorage.setItem(
      "synapse_active_material_topics",
      JSON.stringify(material.topics || [])
    );


    /*
      Send the COMPLETE material to App.
      App will open QuizPage and pass this material
      to the quiz component.
    */

    if (typeof onTakeQuiz === "function") {

      onTakeQuiz(material);

      return;
    }


    /*
      Fallback in case onTakeQuiz has not been
      connected in App yet.
    */

    localStorage.setItem(
      "synapse_material_id",
      material.materialId
    );

    localStorage.setItem(
      "synapse_material_name",
      material.materialName
    );

    localStorage.setItem(
      "synapse_active_material_topics",
      JSON.stringify(
        material.topics || []
      )
    );

    setActivePage("quiz");
  }


  /* =========================================================
     ASK AI TUTOR
     ========================================================= */

  function askTutor(material) {

    localStorage.setItem(
      "synapse_material_id",
      material.materialId
    );

    localStorage.setItem(
      "synapse_material_name",
      material.materialName
    );

    localStorage.setItem(
      "synapse_active_material_topics",
      JSON.stringify(
        material.topics || []
      )
    );

    setActivePage("tutor");
  }


  /* =========================================================
     GENERATE SUBJECTIVE QUESTIONS
     ========================================================= */

  // Convert strings, arrays, and nested objects into safe text.
  function getSafeText(value, fields = []) {
    if (typeof value === "string") {
      return value.trim();
    }

    if (typeof value === "number") {
      return String(value);
    }

    if (Array.isArray(value)) {
      return value
        .map((item) => getSafeText(item, fields))
        .filter(Boolean)
        .join("\n");
    }

    if (value && typeof value === "object") {
      const keys = [
        ...fields,
        "text",
        "content",
        "question",
        "answer",
        "name",
        "title",
        "topic",
        "value",
      ];

      for (const key of [...new Set(keys)]) {
        if (value[key] !== undefined && value[key] !== value) {
          const result = getSafeText(value[key], fields);
          if (result) return result;
        }
      }
    }

    return "";
  }

  function getTopicName(topic) {
    return getSafeText(topic, [
      "topic",
      "name",
      "title",
      "label",
    ]);
  }

  async function generateSubjective() {
    if (!selectedMaterial) return;

    // Convert topic objects to strings before sending to FastAPI.
    const topics = (
      Array.isArray(selectedMaterial.topics)
        ? selectedMaterial.topics
        : []
    )
      .map(getTopicName)
      .filter(Boolean);

    if (topics.length === 0) {
      setGenerationError(
        "No valid topics were found. Please reopen AI Tutor and check your uploaded material."
      );
      return;
    }

    if (Number(questionCount) < topics.length) {
      setGenerationError(
        `This material has ${topics.length} topics. Select at least ${topics.length} questions to cover every topic.`
      );
      return;
    }

    try {
      setGenerating(true);
      setGenerationError("");
      setGeneratedQuestions([]);

      const response = await fetch(
        `${API_BASE}/generate-subjective`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            material_id: selectedMaterial.materialId,
            material_name: selectedMaterial.materialName,
            topics,
            num_questions: Number(questionCount),
            difficulty: difficulty.toLowerCase(),
          }),
        }
      );

      const data = await response.json();

      console.log("Subjective API response:", data);

      if (!response.ok) {
        const detail = getSafeText(data?.detail);
        throw new Error(
          detail || "Could not generate subjective questions."
        );
      }

      if (!Array.isArray(data?.questions)) {
        throw new Error(
          "The backend response does not contain a valid questions array. Check the browser console."
        );
      }

      // Normalize every field before React renders it.
      const questions = data.questions
        .map((item, index) => {
          const questionText =
            typeof item === "string"
              ? item
              : getSafeText(item?.question, [
                "question",
                "question_text",
                "text",
                "content",
              ]);

          const answerText =
            typeof item === "object" && item !== null
              ? getSafeText(item.answer ?? item.model_answer, [
                "answer",
                "model_answer",
                "expected_answer",
                "text",
                "content",
              ])
              : "";

          const topicText =
            typeof item === "object" && item !== null
              ? getSafeText(item.topic, [
                "topic",
                "name",
                "title",
              ])
              : "";

          const rawNumber =
            typeof item === "object" && item !== null
              ? item.question_number
              : null;

          return {
            question_number:
              typeof rawNumber === "number" ||
                typeof rawNumber === "string"
                ? rawNumber
                : index + 1,
            topic: topicText || topics[index % topics.length],
            question: questionText,
            answer: answerText,
            studentAnswer: "",
          };
        })
        .filter((item) => item.question.length > 0);

      if (questions.length === 0) {
        console.error("Invalid generated questions:", data.questions);

        throw new Error(
          "The AI response did not contain readable question text. Check the backend response in the browser console."
        );
      }

      setGeneratedQuestions(questions);
    } catch (error) {
      console.error("Subjective generation error:", error);

      setGenerationError(
        error.message ||
        "Something went wrong while generating questions."
      );
    } finally {
      setGenerating(false);
    }
  }

  /* =========================================================
   PDF HELPERS
   ========================================================= */

  function getSafeFileName() {

    if (!selectedMaterial) {
      return "Synapse_Exam";
    }


    return selectedMaterial
      .materialName
      .replace(
        /\.[^/.]+$/,
        ""
      )
      .replace(
        /[^a-z0-9]+/gi,
        "_"
      );
  }


  function ensurePDFSpace(
    doc,
    y,
    requiredHeight,
    pageHeight
  ) {

    if (
      y + requiredHeight >
      pageHeight - 18
    ) {

      doc.addPage();

      return 20;
    }


    return y;
  }


  /* =========================================================
     DOWNLOAD QUESTIONS + ANSWERS PDF
     ========================================================= */

  async function downloadCompletePDF() {

    if (
      !selectedMaterial ||
      generatedQuestions.length === 0
    ) {
      return;
    }


    try {

      const { jsPDF } =
        await import(
          "jspdf"
        );


      const doc =
        new jsPDF({
          unit: "mm",
          format: "a4",
        });


      const pageWidth =
        doc.internal.pageSize.getWidth();


      const pageHeight =
        doc.internal.pageSize.getHeight();


      const margin = 18;


      const contentWidth =
        pageWidth -
        margin * 2;


      let y = 20;


      /* HEADER */

      doc.setFont(
        "helvetica",
        "bold"
      );

      doc.setFontSize(18);

      doc.text(
        "SYNAPSE",
        margin,
        y
      );


      y += 8;


      doc.setFontSize(14);

      doc.text(
        "AI Exam Preparation",
        margin,
        y
      );


      y += 8;


      doc.setFont(
        "helvetica",
        "normal"
      );

      doc.setFontSize(10);


      const materialText =
        `Material: ${selectedMaterial.materialName}`;


      const materialLines =
        doc.splitTextToSize(
          materialText,
          contentWidth
        );


      doc.text(
        materialLines,
        margin,
        y
      );


      y +=
        materialLines.length * 5 +
        1;


      doc.text(
        `Difficulty: ${difficulty}`,
        margin,
        y
      );


      y += 5;


      doc.text(
        `Total Questions: ${generatedQuestions.length}`,
        margin,
        y
      );


      y += 10;


      /* INSTRUCTIONS */

      doc.setFont(
        "helvetica",
        "bold"
      );

      doc.setFontSize(11);

      doc.text(
        "How to use this study set",
        margin,
        y
      );


      y += 6;


      doc.setFont(
        "helvetica",
        "normal"
      );

      doc.setFontSize(9);


      const instructionText =
        "Try answering each question yourself before checking the answer. Focus on definitions, concepts, explanations, comparisons, applications, and important exam points.";


      const instructionLines =
        doc.splitTextToSize(
          instructionText,
          contentWidth
        );


      doc.text(
        instructionLines,
        margin,
        y
      );


      y +=
        instructionLines.length * 4.5 +
        8;


      /* QUESTIONS + ANSWERS */

      generatedQuestions.forEach(
        (item, index) => {

          const topic =
            item.topic ||
            "General";


          const question =
            item.question ||
            "Question unavailable";


          const answer =
            item.answer ||
            "Answer unavailable";


          y = ensurePDFSpace(
            doc,
            y,
            15,
            pageHeight
          );


          doc.setFont(
            "helvetica",
            "bold"
          );

          doc.setFontSize(9);


          doc.text(
            topic,
            margin,
            y
          );


          y += 5;


          doc.setFont(
            "helvetica",
            "bold"
          );

          doc.setFontSize(10);


          const questionLines =
            doc.splitTextToSize(
              `${item.question_number || index + 1}. ${question}`,
              contentWidth
            );


          y = ensurePDFSpace(
            doc,
            y,
            questionLines.length * 5 +
            10,
            pageHeight
          );


          doc.text(
            questionLines,
            margin,
            y
          );


          y +=
            questionLines.length * 5 +
            5;


          y = ensurePDFSpace(
            doc,
            y,
            12,
            pageHeight
          );


          doc.setFont(
            "helvetica",
            "bold"
          );

          doc.setFontSize(10);


          doc.text(
            "Answer:",
            margin,
            y
          );


          y += 5;


          doc.setFont(
            "helvetica",
            "normal"
          );

          doc.setFontSize(10);


          const answerLines =
            doc.splitTextToSize(
              answer,
              contentWidth
            );


          answerLines.forEach(
            (line) => {

              y = ensurePDFSpace(
                doc,
                y,
                6,
                pageHeight
              );


              doc.text(
                line,
                margin,
                y
              );


              y += 5;

            }
          );


          y += 7;

        }
      );


      doc.save(
        `${getSafeFileName()}_Exam_Preparation.pdf`
      );


    } catch (error) {

      console.error(
        "Complete PDF error:",
        error
      );


      alert(
        "Could not create the exam preparation PDF."
      );
    }
  }


  /* =========================================================
     PAGE
     ========================================================= */

  return (

    <div className="simple-page">

      {/* PAGE HEADING */}

      <div className="page-heading">

        <div>

          <p className="eyebrow">
            STUDY & EXAM PREPARATION
          </p>


          <h1>
            Learning Materials
          </h1>


          <p>
            Study your uploaded materials,
            review important topics, and
            prepare for exams directly in
            Synapse.
          </p>

        </div>

      </div>


      {/* INTRO CARD */}

      <div className="materials-intro-card">

        <div>

          <p>
            Select a material to practice
            short questions from every
            detected topic, take an adaptive
            quiz, ask the AI Tutor questions,
            or download your complete exam
            preparation paper.
          </p>

        </div>

      </div>


      {/* LIBRARY HEADER */}

      <div className="materials-library-header">

        <div>

          <span className="eyebrow">
            YOUR LIBRARY
          </span>


          <h2>
            Study Materials
          </h2>

        </div>


        <span className="materials-count">

          {materials.length} material
          {materials.length !== 1
            ? "s"
            : ""}

        </span>

      </div>


      {/* EMPTY STATE */}

      {materials.length === 0 ? (

        <div className="materials-empty-card">

          <div className="materials-empty-icon">

            <span className="material-symbols-outlined">
              menu_book
            </span>

          </div>


          <h2>
            No learning materials yet
          </h2>


          <p>
            Upload a PDF, PPT, or PPTX from
            AI Tutor. Once Synapse processes
            it, your material and detected
            topics will appear here.
          </p>


          <button
            className="primary-btn"
            onClick={() =>
              setActivePage("tutor")
            }
          >
            Upload Your First Material
          </button>

        </div>

      ) : (

        <div className="materials-grid">

          {materials.map(
            (material) => (

              <div
                key={
                  material.materialId
                }
                className="material-learning-card"
              >

                {/* MATERIAL HEADER */}

                <div className="material-card-top">

                  <div className="material-card-file-icon">

                    <span className="material-symbols-outlined">
                      description
                    </span>

                  </div>


                  <span className="material-ready-badge">

                    <span />

                    Ready

                  </span>

                </div>


                {/* MATERIAL NAME */}

                <h3>
                  {material.materialName}
                </h3>


                {/* TOPIC COUNT */}

                <p className="material-card-meta">

                  {material.topics?.length || 0}{" "}
                  topics detected

                </p>


                {/* TOPIC PREVIEW */}

                {material.topics?.length > 0 && (

                  <div className="material-topic-preview">


                    {material.topics
                      .slice(0, 8)
                      .map((topic, index) => {
                        const normalized = normalizeTopic(topic, index);

                        return (
                          <span key={normalized.id}>
                            {normalized.name}
                          </span>
                        );
                      })}

                  </div>

                )}


                <div className="material-card-divider" />


                {/* =================================================
                    EXAM PREPARATION
                    ================================================= */}

                {/* <div className="material-ai-label">
                  AI EXAM PREPARATION
                </div> */}


                {/* SHORT QUESTIONS */}

                <button
                  className="subjective-practice-btn"
                  onClick={() =>
                    openSubjectivePractice(
                      material
                    )
                  }
                >

                  <span className="material-symbols-outlined">
                    edit_note
                  </span>


                  Short Questions


                  <span className="material-symbols-outlined arrow">
                    arrow_forward
                  </span>

                </button>


                {/* =================================================
                    ADAPTIVE QUIZ
                    ================================================= */}

                <button
                  className="subjective-practice-btn"
                  onClick={() =>
                    openAdaptiveQuiz(
                      material
                    )
                  }
                >

                  <span className="material-symbols-outlined">
                    quiz
                  </span>


                  Adaptive Quiz


                  <span className="material-symbols-outlined arrow">
                    arrow_forward
                  </span>

                </button>


                {/* AI TUTOR */}

                <button
                  className="material-tutor-btn"
                  onClick={() =>
                    askTutor(material)
                  }
                >

                  <span className="material-symbols-outlined">
                    smart_toy
                  </span>


                  Ask AI Tutor

                </button>

              </div>

            )
          )}

        </div>

      )}


      {/* =========================================================
          SUBJECTIVE PRACTICE MODAL
          ========================================================= */}

      {showPractice &&
        selectedMaterial && (

          <div
            className="subjective-modal-overlay"
            onClick={() =>
              setShowPractice(false)
            }
          >

            <div
              className="subjective-modal"
              onClick={(event) =>
                event.stopPropagation()
              }
            >

              {/* MODAL HEADER */}

              <div className="subjective-modal-header">

                <div>

                  <span className="eyebrow">
                    AI EXAM PREPARATION
                  </span>


                  <h2>
                    Short Questions
                  </h2>


                  <p>
                    {selectedMaterial.materialName}
                  </p>

                </div>


                <button
                  className="modal-close-btn"
                  onClick={() =>
                    setShowPractice(false)
                  }
                >
                  ×
                </button>

              </div>


              {/* =================================================
                  GENERATION SETTINGS
                  ================================================= */}

              {generatedQuestions.length === 0 ? (

                <>

                  <div className="subjective-info-card">

                    <div>

                      <strong>
                        Prepare for your exam
                      </strong>


                      <span>
                        Synapse creates
                        university-style short
                        questions from your actual
                        study material. Every
                        detected topic is included,
                        with priority given to
                        important exam concepts.
                      </span>

                    </div>

                  </div>


                  <div className="subjective-settings">

                    {/* QUESTION COUNT */}

                    <div className="subjective-setting">

                      <label>
                        Number of Questions
                      </label>


                      <div className="setting-options">

                        {[10, 20, 30, 50].map(
                          (number) => {

                            const disabled =
                              number <
                              selectedMaterial
                                .topics
                                .length;


                            return (

                              <button
                                key={number}
                                disabled={
                                  disabled
                                }
                                className={
                                  questionCount ===
                                    number
                                    ? "selected"
                                    : ""
                                }
                                onClick={() =>
                                  setQuestionCount(
                                    number
                                  )
                                }
                              >

                                {number}

                              </button>

                            );

                          }
                        )}

                      </div>


                      <small>

                        Every topic must be
                        covered. This material
                        has{" "}

                        {
                          selectedMaterial
                            .topics
                            .length
                        }{" "}

                        topics.

                      </small>

                    </div>


                    {/* DIFFICULTY */}

                    <div className="subjective-setting">

                      <label>
                        Difficulty
                      </label>


                      <div className="setting-options">

                        {[
                          "Easy",
                          "Medium",
                          "Hard",
                        ].map(
                          (level) => (

                            <button
                              key={level}
                              className={
                                difficulty ===
                                  level
                                  ? "selected"
                                  : ""
                              }
                              onClick={() =>
                                setDifficulty(
                                  level
                                )
                              }
                            >

                              {level}

                            </button>

                          )
                        )}

                      </div>

                    </div>

                  </div>


                  {/* TOPIC SUMMARY */}

                  <div className="subjective-topic-summary">

                    <div className="subjective-topic-summary-header">

                      <strong>
                        Topics Included
                      </strong>


                      {/* <span>

                        {
                          selectedMaterial
                            .topics
                            .length
                        }{" "}

                        topics

                      </span> */}

                    </div>


                    <div className="subjective-topic-grid">

                      {selectedMaterial.topics.map(
                        (
                          topic,
                          index
                        ) => {

                          const topicName =
                            getTopicName(topic) || "Untitled Topic";

                          return (

                            <div
                              key={
                                `${topicName}-${index}`
                              }
                            >

                              <span>
                                {index + 1}
                              </span>


                              {topicName}

                            </div>

                          );

                        }
                      )}

                    </div>

                  </div>


                  {/* ERROR */}

                  {generationError && (

                    <div className="subjective-error">

                      {generationError}

                    </div>

                  )}


                  {/* GENERATE */}

                  <button
                    className="primary-btn generate-paper-btn"
                    onClick={
                      generateSubjective
                    }
                    disabled={
                      generating ||
                      questionCount <
                      selectedMaterial
                        .topics
                        .length
                    }
                  >

                    {generating ? (

                      <>

                        <span className="button-spinner" />

                        Generating Questions...

                      </>

                    ) : (

                      <>
                        Generate Short Questions
                      </>

                    )}

                  </button>

                </>

              ) : (

                /* =================================================
                   GENERATED QUESTIONS
                   ================================================= */

                <>

                  <div className="generated-success">

                    <div>

                      <strong>
                        Practice paper ready
                      </strong>


                      <span>

                        {
                          generatedQuestions.length
                        }{" "}

                        questions generated across{" "}

                        {
                          selectedMaterial
                            .topics
                            .length
                        }{" "}

                        topics.

                      </span>

                    </div>

                  </div>


                  {/* DOWNLOAD */}

                  <div className="exam-download-actions">

                    <button
                      className="download-paper-btn"
                      onClick={
                        downloadCompletePDF
                      }
                    >

                      <span className="material-symbols-outlined">
                        download
                      </span>


                      Download

                    </button>

                  </div>


                  {/* STUDY SET */}

                  <div className="generated-question-list">

                    <div className="study-section-heading">

                      <div>

                        <span className="eyebrow">
                          YOUR STUDY SET
                        </span>


                        <h3>
                          Questions & Answers
                        </h3>


                        <p>
                          Try answering each
                          question yourself
                          before checking the
                          answer.
                        </p>

                      </div>


                      <span className="study-question-count">

                        {
                          generatedQuestions.length
                        }{" "}

                        questions

                      </span>

                    </div>


                    {/* QUESTIONS */}

                    {generatedQuestions.map(
                      (
                        item,
                        index
                      ) => (

                        <div
                          key={
                            item.question_number ||
                            `${item.topic}-${index}`
                          }
                          className="generated-question"
                        >

                          <div className="question-number">

                            {
                              item.question_number ||
                              index + 1
                            }

                          </div>


                          <div className="question-content">

                            <small className="question-topic">

                              {
                                item.topic ||
                                "General"
                              }

                            </small>


                            <h4 className="question-text">

                              {
                                item.question ||
                                "Question unavailable"
                              }

                            </h4>


                            <div className="answer-box">

                              <div className="answer-header">

                                <strong>
                                  Answer
                                </strong>

                              </div>


                              <p className="answer-text">

                                {
                                  item.answer ||
                                  "Answer unavailable"
                                }

                              </p>

                            </div>

                          </div>

                        </div>

                      )
                    )}

                  </div>


                  {/* BOTTOM ACTIONS */}

                  <div className="generated-bottom-actions">

                    <button
                      className="secondary-btn"
                      onClick={() => {

                        setGeneratedQuestions(
                          []
                        );

                        setGenerationError("");

                      }}
                    >

                      Change Settings

                    </button>


                    <button
                      className="primary-btn"
                      onClick={
                        downloadCompletePDF
                      }
                    >

                      <span className="material-symbols-outlined">
                        download
                      </span>


                      Download

                    </button>

                  </div>

                </>

              )}

            </div>

          </div>

        )}

    </div>
  );
}


/* =========================================================
   ADAPTIVE QUIZ
   ========================================================= */

function AdaptiveQuiz({ material, onQuizComplete }) {
  const materialId = material?.materialId || "";

  const [topics, setTopics] = useState([]);
  const [quizId, setQuizId] = useState(null);
  const [question, setQuestion] = useState(null);
  const [selected, setSelected] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [loadingTopicIndex, setLoadingTopicIndex] = useState(null);
  const [error, setError] = useState("");
  const [nextQuestion, setNextQuestion] = useState(null);
  const [questionNumber, setQuestionNumber] =
    useState(1);
  const [totalQuestions, setTotalQuestions] =
    useState(5);
  const [progress, setProgress] = useState(0);
  const [activeTopicIndex, setActiveTopicIndex] = useState(null);
  const [quizRunId, setQuizRunId] = useState(null);
  const [hasStartedSeries, setHasStartedSeries] = useState(false);
  const [isRestartOnly, setIsRestartOnly] = useState(false);
  const [singleTopicMode, setSingleTopicMode] = useState(false);
  const [topicCorrect, setTopicCorrect] = useState(0);
  const [overallScore, setOverallScore] = useState({
    answered: 0,
    correct: 0,
  });
  const loadTopics = async () => {

    if (!materialId) {
      setError(
        "No learning material is selected. Please open Adaptive Quiz from a learning material."
      );
      return;
    }

    try {

      setTopicsLoading(true);
      setError("");

      const response = await axios.post(
        `${API_BASE}/topics`,
        {
          material_id: materialId,
        }
      );

      console.log("TOPICS:", response.data);

      const loadedTopics = response.data.topics || [];
      setTopics(loadedTopics);
      localStorage.setItem(
        "synapse_active_material_topics",
        JSON.stringify(loadedTopics)
      );

      const pendingTopic = localStorage.getItem("synapse_selected_topic");
      if (pendingTopic) {
        const pendingIndex = loadedTopics.findIndex((topic) => {
          const name = typeof topic === "string"
            ? topic
            : topic?.topic || topic?.name || topic?.title;
          return String(name || "").toLowerCase() === pendingTopic.toLowerCase();
        });

        if (pendingIndex >= 0) {
          setSingleTopicMode(true);
          await startQuiz(pendingTopic, pendingIndex);
        }
      }

    } catch (err) {

      console.error(err);

      setError(
        err.response?.data?.detail ||
        "Could not load topics."
      );

    } finally {

      setTopicsLoading(false);

    }
  };


const startQuiz = async (
  topicToPractice = null,
  topicIndex = null,
  restartSeries = false
) => {
  if (!materialId) {
    setError(
      "No learning material is selected. Please open Learning Materials and select your material first."
    );
    return;
  }

  if (
    !topics.length &&
    !topicToPractice &&
    !localStorage.getItem("synapse_selected_topic")
  ) {
    setError("Please click Load Topics first.");
    return;
  }

  try {
    setLoading(true);
    setLoadingTopicIndex(topicIndex);
    setError("");

    const startsNewSeries = !hasStartedSeries || restartSeries;
    const runId = startsNewSeries
      ? `run_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
      : quizRunId;

    if (startsNewSeries) {
      setQuizRunId(runId);
      setHasStartedSeries(true);
      setIsRestartOnly(restartSeries);
      if (restartSeries) setSingleTopicMode(true);
      setOverallScore({ answered: 0, correct: 0 });
      localStorage.setItem("synapse_active_quiz_run", runId);
    }

    const selectedTopic =
      topicToPractice ||
      localStorage.getItem("synapse_selected_topic");

    const normalizedTopics = topics
      .map((item) => {
        if (typeof item === "string") {
          return {
            topic: item.trim(),
            subtopics: [],
          };
        }

        if (!item || typeof item !== "object") {
          return null;
        }

        return {
          topic: String(
            item.topic || item.name || item.title || ""
          ).trim(),
          subtopics: Array.isArray(item.subtopics)
            ? item.subtopics.filter(
                (subtopic) => typeof subtopic === "string"
              )
            : [],
        };
      })
      .filter((item) => item && item.topic);

    const quizTopics = selectedTopic
      ? [
          {
            topic: selectedTopic,
            subtopics: [],
          },
        ]
      : normalizedTopics;

    const response = await axios.post(
      `${API_BASE}/quiz/start`,
      {
        material_id: materialId,
        topics: quizTopics,
        num_questions: 5,
        difficulty: (localStorage.getItem("synapse_difficulty") || "Adaptive").toLowerCase(),
      }
    );

    console.log("QUIZ START:", response.data);

    setQuizId(response.data.quiz_id);
    setActiveTopicIndex(topicIndex);
    setTopicCorrect(0);
    setQuestion(response.data.question);
    setNextQuestion(null);

    setQuestionNumber(
      response.data.quiz_progress?.question_number || 1
    );

    setTotalQuestions(
      response.data.quiz_progress?.total_questions || 5
    );

    setProgress(
      response.data.quiz_progress?.percentage_completed || 0
    );

    setSelected("");
    setResult(null);

    if (selectedTopic) {
      localStorage.removeItem("synapse_selected_topic");
    }
  } catch (err) {
    console.error(err);

    setError(
      err.response?.data?.detail ||
      "Could not start quiz."
    );
  } finally {
    setLoading(false);
    setLoadingTopicIndex(null);
  }
};


  const submitAnswer = async () => {

    if (!selected) {

      setError(
        "Please select an answer."
      );

      return;
    }

    if (!quizId) {

      setError(
        "Quiz has not started."
      );

      return;
    }

    try {

      setLoading(true);
      setError("");

      const response = await axios.post(
        `${API_BASE}/quiz/answer`,
        {
          quiz_id: quizId,
          answer: selected,
        }
      );

      console.log(
        "ANSWER RESULT:",
        response.data
      );

      /*
        IMPORTANT:
  
        Keep the current question on screen.
  
        The result belongs to the question
        the student just answered.
      */

      const analyticsKey = "synapse_quiz_analytics";

      const savedAnswers = JSON.parse(
        localStorage.getItem(analyticsKey) || "[]"
      );
      const answerWasCorrect = Boolean(
        response.data?.answered_question?.correct
      );

      setOverallScore((score) => ({
        answered: score.answered + 1,
        correct: score.correct + (answerWasCorrect ? 1 : 0),
      }));

      if (answerWasCorrect) {
        setTopicCorrect((score) => score + 1);
      }

      savedAnswers.push({
        quizId,
        quizRunId,
        materialId,
        topic: question?.topic || "General",
        subtopic: question?.subtopic || question?.topic || "General",
        correct: answerWasCorrect,
        timestamp: new Date().toISOString(),
      });

      localStorage.setItem(
        analyticsKey,
        JSON.stringify(savedAnswers)
      );
      window.dispatchEvent(
  new Event("quiz-analytics-updated")
);

      setResult(response.data);

      setProgress(
        response.data.quiz_progress
          ?.percentage_completed || 0
      );

      // Open Learning Analytics after the final answer
      // Open Learning Analytics after the final answer
      // Keep the quiz screen visible after the final answer.
// The user will open Analytics using a separate button.
if (response.data.completed) {
  setNextQuestion(null);
  return;
}

      /*
        Store the next question separately.
  
        DO NOT call setQuestion() here.
      */

      if (
        !response.data.completed &&
        response.data.next_question
      ) {

        setNextQuestion(
          response.data.next_question
        );

      } else {

        setNextQuestion(null);

      }

    } catch (err) {

      console.error(err);

      setError(
        err.response?.data?.detail ||
        "Could not submit answer."
      );

    } finally {

      setLoading(false);

    }
  };
  const handleNextQuestion = () => {

    if (!nextQuestion) {
      return;
    }

    setQuestion(nextQuestion);

    /*
      Backend tells us which question
      comes next.
    */

    if (
      result?.quiz_progress
        ?.next_question_number
    ) {

      setQuestionNumber(
        result.quiz_progress
          .next_question_number
      );

    } else {

      setQuestionNumber(
        (current) => current + 1
      );

    }

    setSelected("");

    setResult(null);

    setNextQuestion(null);

    setError("");
  };

  /* =====================================================
     NO MATERIAL
     ===================================================== */

  if (!materialId) {

    return (
      <div className="simple-page">

        <div className="page-heading">

          <div>

            <p className="eyebrow">
              Personalized Assessment
            </p>

            <h1>
              Adaptive Quiz 📝
            </h1>

            <p>
              Select a learning material first
              to start your adaptive quiz.
            </p>

          </div>

        </div>


        <div className="simple-card">

          <h2>
            No Material Selected
          </h2>

          <p>
            Go to Learning Materials and click
            <strong> Adaptive Quiz </strong>
            on the material you want to practice.
          </p>

        </div>

      </div>
    );
  }


  /* =====================================================
     BEFORE QUIZ
     ===================================================== */

  if (!quizId) {

    return (
      <div className="simple-page">

        <div className="page-heading">

          <div>

            <p className="eyebrow">
              Personalized Assessment
            </p>

            <h1>
              Adaptive Quiz 📝
            </h1>

            <p>
              Questions are adapted according
              to your learning performance.
            </p>

          </div>

        </div>


        <div className="simple-card">

          <h2>
            {material?.materialName || "Adaptive Quiz"}
          </h2>

          <p>
            Synapse will use the topics detected
            from this learning material to create
            your personalized quiz.
          </p>


          <button
            className="primary-btn"
            onClick={loadTopics}
            disabled={
              topicsLoading ||
              loading ||
              result !== null
            }
          >

            {topicsLoading
              ? "Loading Topics..."
              : "Load Topics"}

          </button>


          {topics.length > 0 && (

            <div
              style={{
                marginTop: "25px",
              }}
            >

              <h3>
                Topics Found
              </h3>
            {topics.map((topic, index) => {
  const topicName = typeof topic === "string"
    ? topic
    : topic?.topic || topic?.name || topic?.title;

  if (!topicName) return null;

  return (
  <button
    key={topicName}
    type="button"
    onClick={() => startQuiz(topicName, index)}
    disabled={loading || topicsLoading}
    style={{
      display: "block",
      width: "100%",
      padding: "16px",
      marginBottom: "10px",
      textAlign: "left",
      border: "1px solid #ddd",
      borderRadius: "10px",
      background: "#fff",
      color: "#222",
      cursor: loading ? "wait" : "pointer",
    }}
  >
    <strong>
      {index + 1}. {topicName}
    </strong>

    <div style={{ marginTop: "8px", color: "#2563eb" }}>
      {loadingTopicIndex === index
        ? "Creating quiz..."
        : "Start 5-question quiz →"}
    </div>
  </button>
  );
})}

            </div>
          )}

          {error && (

            <p
              style={{
                color: "red",
                marginTop: "15px",
              }}
            >
              {error}
            </p>

          )}

        </div>

      </div>
    );
  }


  /* =====================================================
     QUIZ SCREEN
     ===================================================== */

  return (
    <div className="simple-page">

      <div className="page-heading">

        <div>

          <p className="eyebrow">
            Personalized Assessment
          </p>

          <h1>
            Adaptive Quiz 📝
          </h1>

          <p>
            {material?.materialName}
          </p>

        </div>

      </div>


      {question && (

        <div className="quiz-card">

          <div className="quiz-top">

            <span>

              Question{" "}

              {questionNumber}

              {" of "}

              {totalQuestions}

            </span>

            <span>

              {question.topic}
              {" • "}
              {question.difficulty}

            </span>

          </div>


          <div
            style={{
              width: "100%",
              height: "8px",
              background: "#e5e7eb",
              borderRadius: "999px",
              overflow: "hidden",
              marginTop: "12px",
            }}
          >
            <div
              style={{
                width: `${progress}%`,
                height: "100%",
                background: "#22c55e",
                borderRadius: "999px",
                transition: "width 0.4s ease",
              }}
            />
          </div>

          <p
            style={{
              marginTop: "6px",
              fontSize: "13px",
              opacity: 0.65,
            }}
          >
            {progress}% completed
          </p>


          <p
            style={{
              opacity: 0.6,
              marginTop: "15px",
            }}
          >

            Subtopic:{" "}

            <strong>
              {question.subtopic || question.topic}
            </strong>

          </p>


          <h2>
            {question.question}
          </h2>


          {/* OPTIONS */}

          {Object.entries(
            question.options || {}
          ).map(
            ([key, value]) => (

              <button
                key={key}
                className={`quiz-option ${selected === key
                    ? "selected"
                    : ""
                  }`}
                onClick={() =>
                  setSelected(key)
                }
                disabled={loading || result !== null}
              >

                <span className="option-circle">

                  {selected === key
                    ? "✓"
                    : ""}

                </span>

                <strong>
                  {key}.
                </strong>{" "}

                {value}

              </button>

            )
          )}
          
<button
  className="primary-btn"
  onClick={submitAnswer}
  disabled={loading || !selected || result !== null}
>
  {loading ? "Submitting..." : "Submit Answer"}
</button>



          
          {/* ANSWER EXPLANATION */}

          {result?.answered_question && (

            <div
              className="simple-card"
              style={{
                marginTop: "20px",
              }}
            >

              <h3>

                {result.answered_question.correct
                  ? "✅ Correct!"
                  : "❌ Incorrect"}

              </h3>


              <p>

                <strong>
                  Your answer:
                </strong>{" "}

                {
                  result.answered_question
                    .your_answer
                }

              </p>


              <p>

                <strong>
                  Correct answer:
                </strong>{" "}

                {
                  result.answered_question
                    .correct_answer
                }

              </p>


              <p>

                <strong>
                  Explanation:
                </strong>

              </p>


              <p>
                {
                  result.answered_question
                    .explanation
                }
              </p>

            </div>

          )}


          {/* AI ADAPTATION */}

          {result?.adaptive_decision && (

            <div
              className="ai-reason-card"
              style={{
                marginTop: "20px",
              }}
            >
              {/* 
              <span className="material-symbols-outlined">
                auto_awesome
              </span> */}


              <div>

                <strong>
                  AI Adaptive Decision
                </strong>


                <p>

                  Difficulty:{" "}

                  {
                    result.adaptive_decision
                      .previous_difficulty
                  }

                  {" → "}

                  {
                    result.adaptive_decision
                      .next_difficulty
                  }

                </p>


                <p>

                  Next topic:{" "}

                  {
                    result.adaptive_decision
                      .next_topic
                  }

                </p>


                <p>

                  Next subtopic:{" "}

                  {
                    result.adaptive_decision
                      .next_subtopic
                  }

                </p>

              </div>

            </div>

          )}
          {/* NEXT QUESTION */}

          {result &&
            !result.completed &&
            nextQuestion && (

              <div
                style={{
                  marginTop: "25px",
                  display: "flex",
                  justifyContent: "flex-end",
                }}
              >

                <button
                  className="primary-btn"
                  onClick={handleNextQuestion}
                >

                  Next Question →

                </button>

              </div>

            )}

        </div>

      )}


      {/* COMPLETED */}

      
{/* COMPLETED */}
{result?.completed &&
  !singleTopicMode &&
  !isRestartOnly &&
  activeTopicIndex < topics.length - 1 && (
  <div className="simple-card">
    <h2>🎉 Topic Quiz Completed!</h2>

    <p>
      You scored {topicCorrect} out of {totalQuestions} for this topic.
    </p>

    <button
      className="primary-btn"
      onClick={() => {
        const nextTopic = topics[activeTopicIndex + 1];
        const nextTopicName = typeof nextTopic === "string"
          ? nextTopic
          : nextTopic?.topic || nextTopic?.name || nextTopic?.title;
        if (nextTopicName) startQuiz(nextTopicName, activeTopicIndex + 1);
      }}
      disabled={loading}
    >
      {loading ? "Loading next quiz..." : "Next Topic →"}
    </button>
  </div>
)}

{result?.completed &&
  (singleTopicMode || isRestartOnly || activeTopicIndex === topics.length - 1) && (
  <div className="simple-card">
    <h2>
      {singleTopicMode || isRestartOnly
        ? "🎉 Topic Quiz Completed!"
        : "🎉 All Topic Quizzes Completed!"}
    </h2>
    <p>
      Final score: {overallScore.correct} out of {overallScore.answered} questions
      {overallScore.answered > 0 &&
        ` (${Math.round((overallScore.correct / overallScore.answered) * 100)}%)`}
    </p>
    <button
      className="primary-btn"
      onClick={() => {
        if (typeof onQuizComplete === "function") onQuizComplete();
      }}
    >
      View Learning Analytics →
    </button>
    <button
      className="secondary-btn"
      onClick={() => {
        const lastTopic = topics[activeTopicIndex];
        const topicName = typeof lastTopic === "string"
          ? lastTopic
          : lastTopic?.topic || lastTopic?.name || lastTopic?.title;
        if (topicName) startQuiz(topicName, activeTopicIndex, true);
      }}
      disabled={loading}
    >
      {loading ? "Starting new questions..." : "Restart Last Topic →"}
    </button>
  </div>
)}


    </div>
  );
}

/* =========================================================
   ANALYTICS
   ========================================================= */

const MAIN_TOPICS = [
  {
    id: "alphabets-symbols",
    name: "Alphabets and Symbols",
    description: "Alphabets, symbols and notation Σ",
  },
  {
    id: "words-strings",
    name: "Words and Strings",
    description: "Words, strings and string length",
  },
  {
    id: "language-definitions",
    name: "Languages and Their Definitions",
    description: "Descriptive, recursive, RE and FA",
  },
  {
    id: "formal-informal",
    name: "Formal vs Informal Languages",
    description: "Syntax and meaning",
  },
  {
    id: "palindromes",
    name: "Palindromes as a Language",
    description: "Reversal and palindrome properties",
  },
  {
    id: "counting-strings",
    name: "Counting Strings and Language Size",
    description: "Counting formulas and language size",
  },
  {
    id: "language-examples",
    name: "Language Examples",
    description: "Factorial, odd-length and other languages",
  },
  {
    id: "validity-alphabets",
    name: "Validity of Alphabets",
    description: "Valid and invalid alphabets",
  },
];

function AnalyticsPage({ setActivePage }) {
  const [answers, setAnswers] = useState([]);
  const [analyticsTopics, setAnalyticsTopics] = useState(MAIN_TOPICS);
  const [materialName, setMaterialName] = useState("");

  useEffect(() => {
    const loadAnalytics = () => {
      try {
        const saved = JSON.parse(
          localStorage.getItem("synapse_quiz_analytics") || "[]"
        );
        const activeMaterialId = localStorage.getItem(
          "synapse_quiz_material_id"
        );
        const activeRunId = localStorage.getItem(
          "synapse_active_quiz_run"
        );
        const savedTopics = JSON.parse(
          localStorage.getItem("synapse_active_material_topics") || "[]"
        );

        const scopedAnswers = Array.isArray(saved)
          ? saved.filter((answer) =>
              (!activeMaterialId || answer.materialId === activeMaterialId) &&
              (!activeRunId || answer.quizRunId === activeRunId)
            )
          : [];

        setAnswers(scopedAnswers);
        setMaterialName(
          localStorage.getItem("synapse_quiz_material_name") || ""
        );

        if (Array.isArray(savedTopics) && savedTopics.length > 0) {
          const normalizedTopics = savedTopics
            .map((topic, index) => {
              const name = typeof topic === "string"
                ? topic.trim()
                : String(topic?.topic || topic?.name || topic?.title || "").trim();

              if (!name) return null;

              const subtopics = Array.isArray(topic?.subtopics)
                ? topic.subtopics.filter((subtopic) => typeof subtopic === "string")
                : [];

              return {
                id: `topic-${index}-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
                name,
                description: subtopics.length
                  ? subtopics.join(" · ")
                  : "Topic from your selected learning material.",
              };
            })
            .filter(Boolean);

          setAnalyticsTopics(normalizedTopics);
        } else {
          setAnalyticsTopics(MAIN_TOPICS);
        }
      } catch (error) {
        console.error("Failed to load analytics:", error);
        setAnswers([]);
      }
    };

    loadAnalytics();

    window.addEventListener("focus", loadAnalytics);
    window.addEventListener("quiz-analytics-updated", loadAnalytics);

    return () => {
      window.removeEventListener("focus", loadAnalytics);
      window.removeEventListener(
        "quiz-analytics-updated",
        loadAnalytics
      );
    };
  }, []);

  const attempted = answers.length;

  const correct = answers.filter(
    (answer) => answer.correct === true
  ).length;

  const accuracy = attempted
    ? Math.round((correct / attempted) * 100)
    : 0;

  // Include every topic from the active material and any saved quiz topic.
  const topicsWithResults = [...analyticsTopics];

  answers.forEach((answer) => {
    const savedTopic = String(answer.topic || "").trim();
    if (
      savedTopic &&
      !topicsWithResults.some(
        (topic) => topic.name.toLowerCase() === savedTopic.toLowerCase()
      )
    ) {
      topicsWithResults.push({
        id: `topic-${savedTopic.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
        name: savedTopic,
        description: "Topic from your quiz results.",
      });
    }
  });

  const topicMap = {};

  topicsWithResults.forEach((topic) => {
    topicMap[topic.name] = {
      attempted: 0,
      correct: 0,
    };
  });

  // Match saved answers to the active material's topics.
  answers.forEach((answer) => {
    const savedTopic = String(answer.topic || "").trim();
    const matchedTopic = topicsWithResults.find(
      (topic) => topic.name.toLowerCase() === savedTopic.toLowerCase()
    );
    if (!matchedTopic) return;

    topicMap[matchedTopic.name].attempted += 1;

    if (answer.correct === true) {
      topicMap[matchedTopic.name].correct += 1;
    }
  });

  const topicStats = topicsWithResults.map((topic) => {
    const stats = topicMap[topic.name];

    const topicAccuracy = stats.attempted
      ? Math.round((stats.correct / stats.attempted) * 100)
      : null;

    return {
      ...topic,
      attempted: stats.attempted,
      correct: stats.correct,
      accuracy: topicAccuracy,
    };
  });

  // A topic needs at least five answered questions before
  // being classified as weak.
  const weakAreas = topicStats
    .filter(
      (topic) =>
        topic.attempted >= 5 &&
        topic.accuracy < 70
    )
    .sort((a, b) => a.accuracy - b.accuracy);

  const practicedTopics = topicStats.filter(
    (topic) => topic.attempted > 0
  ).length;

  const startTopicPractice = (topic) => {
    // QuizPage must read this value to start a topic-specific quiz.
    localStorage.setItem(
      "synapse_selected_topic",
      topic.name
    );

    localStorage.setItem(
      "synapse_quiz_question_count",
      "5"
    );

    setActivePage("quiz");
  };

  return (
    <div className="simple-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Performance Insights</p>
          <h1>Learning Analytics 📊</h1>
          <p>
            Track {analyticsTopics.length} topics from {materialName || "your learning material"},
            identify weak areas, and practice where you need improvement.
          </p>
        </div>
      </div>

      {/* Overall statistics */}
      <div className="stats-grid">
        <StatCard
          label="Questions Attempted"
          value={attempted}
          footer={`${correct} correct answers`}
          icon="quiz"
        />

        <StatCard
          label="Overall Accuracy"
          value={`${accuracy}%`}
          footer="Across all saved attempts"
          icon="target"
        />

        <StatCard
          label="Topics Practiced"
          value={`${practicedTopics}/${analyticsTopics.length}`}
          footer="Topics with at least one answer"
          icon="menu_book"
        />
      </div>

      {/* Weak topic summary */}
      <div className="simple-card">
        <h2>Weak Areas</h2>
        <p>
          Topics with at least five answered questions
          and accuracy below 70%.
        </p>

        {weakAreas.length > 0 ? (
          weakAreas.map((topic) => (
            <div
              className="analytics-topic"
              key={topic.id}
            >
              <div>
                <span>{topic.name}</span>
                <strong>{topic.accuracy}%</strong>
              </div>

              <ProgressBar value={topic.accuracy} />

              <button
                className="primary-btn"
                onClick={() => startTopicPractice(topic)}
              >
                Practice This Topic →
              </button>
            </div>
          ))
        ) : (
          <p>
            {attempted === 0
              ? "Complete a topic quiz to start building your analytics."
              : "No weak topics meet the minimum attempt requirement yet. Keep practicing to build reliable results."}
          </p>
        )}
      </div>

      {/* All active material topic cards */}
      <div className="simple-card">
        <h2>Topic Performance</h2>
        <p>
          Your results across all {analyticsTopics.length} topics in this material.
          Select any topic to practice it.
        </p>

        <div className="analytics-topic-grid">
          {topicStats.map((topic) => (
            <div
              className="analytics-topic-card"
              key={topic.id}
            >
              <div className="analytics-topic-card-header">
                <h3>{topic.name}</h3>

                <strong>
                  {topic.accuracy === null
                    ? "Not attempted"
                    : `${topic.accuracy}%`}
                </strong>
              </div>

              <p>{topic.description}</p>

              {topic.attempted > 0 ? (
                <>
                  <ProgressBar value={topic.accuracy} />

                  <p>
                    {topic.correct} correct out of{" "}
                    {topic.attempted} answered
                  </p>
                </>
              ) : (
                <p>No results saved yet.</p>
              )}

              <button
                className="primary-btn"
                onClick={() => startTopicPractice(topic)}
              >
                {topic.attempted === 0
                  ? "Start Topic Quiz →"
                  : topic.accuracy < 70
                  ? "Practice Again →"
                  : "Quiz This Topic →"}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


/* =========================================================
   SETTINGS
   ========================================================= */


function SettingsPage() {
  const [difficulty, setDifficulty] = useState(
    () => localStorage.getItem("synapse_difficulty") || "Adaptive"
  );

  const [goal, setGoal] = useState(
    () => localStorage.getItem("synapse_daily_goal") || "60"
  );

  const [theme, setTheme] = useState(
    () => localStorage.getItem("synapse_theme") || "light"
  );

  useEffect(() => {
    localStorage.setItem("synapse_difficulty", difficulty);
  }, [difficulty]);

  useEffect(() => {
    localStorage.setItem("synapse_daily_goal", goal);
  }, [goal]);

  useEffect(() => {
    localStorage.setItem("synapse_theme", theme);

    const root = document.documentElement;

    if (theme === "system") {
      root.setAttribute("data-theme", "light");
      root.setAttribute("data-theme-mode", "system");
    } else {
      root.setAttribute("data-theme", theme);
      root.removeAttribute("data-theme-mode");
    }
  }, [theme]);

  return (
    <div className="simple-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Preferences</p>
          <h1>Settings ⚙️</h1>
          <p>Customize your learning experience.</p>
        </div>
      </div>

      <div className="simple-card settings-card">

        {/* Learning Difficulty */}
        <div className="setting-row">
          <div>
            <strong>Learning Difficulty</strong>
            <p>Choose your preferred quiz difficulty.</p>
          </div>

          <div className="radio-options">
            {["Adaptive", "Easy", "Medium", "Hard"].map((item) => (
              <label className="radio-option" key={item}>
                <input
                  type="radio"
                  name="difficulty"
                  value={item}
                  checked={difficulty === item}
                  onChange={() => setDifficulty(item)}
                />
                <span>{item}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Daily Learning Goal */}
        <div className="setting-row">
          <div>
            <strong>Daily Learning Goal</strong>
            <p>
              {goal === "30"
                ? "30 minutes per day"
                : goal === "60"
                ? "1 hour per day"
                : goal === "90"
                ? "1.5 hours per day"
                : "2 hours per day"}
            </p>
          </div>

          <div className="radio-options">
            {[
              { value: "30", label: "30 min" },
              { value: "60", label: "1 hour" },
              { value: "90", label: "1.5 hours" },
              { value: "120", label: "2 hours" },
            ].map((item) => (
              <label className="radio-option" key={item.value}>
                <input
                  type="radio"
                  name="dailyGoal"
                  value={item.value}
                  checked={goal === item.value}
                  onChange={() => setGoal(item.value)}
                />
                <span>{item.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Appearance */}
        <div className="setting-row">
          <div>
            <strong>Appearance</strong>
            <p>Choose your preferred theme.</p>
          </div>

          <div className="radio-options">
            {[
              { value: "light", label: "☀️ Light" },
              { value: "dark", label: "🌙 Dark" },
              { value: "system", label: "💻 System" },
            ].map((item) => (
              <label className="radio-option" key={item.value}>
                <input
                  type="radio"
                  name="appearance"
                  value={item.value}
                  checked={theme === item.value}
                  onChange={() => setTheme(item.value)}
                />
                <span>{item.label}</span>
              </label>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}



/* =========================================================
   DASHBOARD
   ========================================================= */


function DashboardPage({ setActivePage }) {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      try {
        const response = await fetch(`${API_BASE}/dashboard`);

        if (!response.ok) {
          throw new Error(`Dashboard API returned ${response.status}`);
        }

        const result = await response.json();

        if (mounted) {
          setData(result);
          setError("");
        }
      } catch (err) {
        if (mounted) {
          setError(
            "Cannot connect to the learning server. Check that FastAPI is running."
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    // Refresh dashboard data while this page is open.
    const intervalId = setInterval(loadDashboard, 15000);

    return () => {
      mounted = false;
      clearInterval(intervalId);
    };
  }, []);

  const overview = data?.overview || {};
  const mastery = data?.topic_mastery || [];
  const activities = data?.recent_activity || [];

  const weakTopics = mastery.filter(
    (topic) => topic.percentage < 70
  );

  const nextTopic = weakTopics[0];

  const refreshDashboard = async () => {
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/dashboard`);

      if (!response.ok) {
        throw new Error("Refresh failed");
      }

      setData(await response.json());
      setError("");
    } catch {
      setError("Could not refresh dashboard data.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="dashboard live-dashboard">
      <section className="dashboard-intro">
        <div>
          {/* <span className="dashboard-eyebrow">
            SYNAPSE LEARNING SPACE
          </span> */}

          <h1>Welcome back, Hamna 👋</h1>

          <p>
            Your learning progress, quiz performance and
            areas for improvement — all in one place.
          </p>
        </div>

        <button
          className="secondary-btn"
          onClick={refreshDashboard}
          disabled={loading}
        >
          <span className="material-symbols-outlined">
            refresh
          </span>
          {loading ? "Refreshing..." : "Refresh data"}
        </button>
      </section>

      {error && (
        <div className="dashboard-error" role="alert">
          <span className="material-symbols-outlined">
            cloud_off
          </span>
          <div>
            <strong>Dashboard connection issue</strong>
            <p>{error}</p>
          </div>
          <button onClick={refreshDashboard}>Retry</button>
        </div>
      )}

      <section className="stats-grid">
        <StatCard
          label="Overall Accuracy"
          value={`${overview.accuracy ?? 0}%`}
          badge="Live quiz data"
          footer="Calculated from answered quiz questions"
          icon="target"
          iconType="purple"
          progress={overview.accuracy ?? 0}
          progressType="primary"
        />

        <StatCard
          label="Questions Answered"
          value={String(overview.questions_answered ?? 0)}
          badge="All recorded sessions"
          footer="Includes answered questions from current sessions"
          icon="task_alt"
          iconType="blue"
          progress={Math.min(
            overview.questions_answered ?? 0,
            100
          )}
          progressType="secondary"
        />

        <StatCard
          label="Completed Quizzes"
          value={String(overview.completed_quizzes ?? 0)}
          badge="Backend records"
          footer="Successfully completed adaptive quizzes"
          icon="quiz"
          iconType="neutral"
          progress={
            (overview.completed_quizzes ?? 0) > 0 ? 100 : 0
          }
          progressType="tertiary"
        />

        <StatCard
          label="Topics Practiced"
          value={String(overview.topics_studied ?? 0)}
          badge="Across quiz attempts"
          footer="Topics with recorded assessment results"
          icon="account_tree"
          iconType="amber"
          progress={Math.min(
            (overview.topics_studied ?? 0) * 10,
            100
          )}
          progressType="amber"
        />
      </section>

      <section className="large-grid">
        <div className="ai-plan">
          <div className="ai-plan-header">
            <span className="ai-badge">
              <span className="material-symbols-outlined">
                auto_awesome
              </span>
              Adaptive Learning
            </span>

            <span className="updated">
              {loading ? "Updating..." : "Connected to API"}
            </span>
          </div>

          <h2>Your Learning Priorities</h2>

          {nextTopic ? (
            <>
              <p className="ai-description">
                Based on your recorded quiz performance,
                focus on <strong>{nextTopic.title}</strong>.
                Your current accuracy for this topic is{" "}
                <strong>{nextTopic.percentage}%</strong>.
              </p>

              <div className="plan-list">
                <div className="plan-item clickable">
                  <span className="material-symbols-outlined purple-text">
                    menu_book
                  </span>

                  <div>
                    <strong>
                      Review {nextTopic.title}
                    </strong>
                    <small>
                      {nextTopic.correct} correct out of{" "}
                      {nextTopic.total} answered
                    </small>
                  </div>
                </div>

                <div className="plan-item clickable">
                  <span className="material-symbols-outlined blue-text">
                    quiz
                  </span>

                  <div>
                    <strong>Practice this topic</strong>
                    <small>
                      Strengthen understanding with another quiz
                    </small>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="dashboard-empty">
              <span className="material-symbols-outlined">
                auto_awesome
              </span>

              <strong>
                {mastery.length
                  ? "Great progress across assessed topics"
                  : "Your learning plan starts with your first quiz"}
              </strong>

              <p>
                {mastery.length
                  ? "No topic is currently below 70%. Keep practicing to maintain your progress."
                  : "Upload your lecture materials and take an adaptive quiz to build your personalized dashboard."}
              </p>
            </div>
          )}

          <div className="plan-buttons">
            <button
              className="primary-btn"
              onClick={() => setActivePage("materials")}
            >
              Open Learning Materials
              <span className="material-symbols-outlined">
                arrow_forward
              </span>
            </button>

            <button
              className="secondary-btn"
              onClick={() => setActivePage("quiz")}
            >
              Practice Quiz
            </button>
          </div>
        </div>

        <div className="mastery-card">
          <div className="section-header">
            <div>
              <h2>Topic Mastery</h2>
              <p>
                Based on actual recorded quiz performance
              </p>
            </div>

            <span className="material-symbols-outlined">
              insights
            </span>
          </div>

          {mastery.length ? (
            <div className="mastery-list">
              {mastery.slice(0, 8).map((topic) => (
                <MasteryItem
                  key={topic.title}
                  title={topic.title}
                  status={topic.status}
                  percentage={topic.percentage}
                  type={
                    topic.percentage >= 85
                      ? "tertiary"
                      : topic.percentage >= 70
                      ? "secondary"
                      : topic.percentage >= 50
                      ? "amber"
                      : "error"
                  }
                  buttonText={
                    topic.percentage >= 70 ? "Review" : "Practice"
                  }
                  onClick={() => setActivePage("quiz")}
                />
              ))}
            </div>
          ) : (
            <div className="dashboard-empty">
              <p>
                Topic mastery will appear after you submit quiz answers.
              </p>
            </div>
          )}

          <div className="mastery-footer">
            <span>
              {mastery.length} assessed topics
            </span>

            <button onClick={() => setActivePage("analytics")}>
              View analytics
              <span className="material-symbols-outlined">
                arrow_outward
              </span>
            </button>
          </div>
        </div>
      </section>

      <section className="bottom-grid">
        <div className="activity-card">
          <div className="section-header">
            <div className="heading-icon">
              <span className="material-symbols-outlined purple-text">
                history
              </span>
              <h2>Recent Quiz Activity</h2>
            </div>

            <span className="activity-filter">
              Live records
            </span>
          </div>

          {activities.length ? (
            <div className="activity-list">
              {activities.map((activity) => (
                <ActivityItem
                  key={activity.quiz_id}
                  type={
                    activity.completed
                      ? "Quiz Completed"
                      : "Quiz In Progress"
                  }
                  time={
                    `${activity.answered} of ${activity.total_questions} answered`
                  }
                  title={activity.topic || "Adaptive Quiz"}
                  description={
                    `Material: ${activity.material_id || "Not specified"} · Difficulty: ${activity.difficulty}`
                  }
                  dot={
                    activity.completed
                      ? "green-dot"
                      : "purple-dot"
                  }
                />
              ))}
            </div>
          ) : (
            <div className="dashboard-empty">
              <p>
                No quiz activity recorded in this server session yet.
              </p>
            </div>
          )}

          <button
            className="history-button"
            onClick={() => setActivePage("analytics")}
          >
            Open Learning Analytics
          </button>
        </div>

        <div className="learning-card">
          <div className="section-header">
            <div className="heading-icon">
              <span className="material-symbols-outlined blue-text">
                school
              </span>
              <h2>Continue Learning</h2>
            </div>
          </div>

          <p className="ai-description">
            Continue with your existing uploaded materials,
            AI Tutor and adaptive quizzes.
          </p>

          <div className="plan-list">
            <div
              className="plan-item clickable"
              onClick={() => setActivePage("materials")}
            >
              <span className="material-symbols-outlined purple-text">
                picture_as_pdf
              </span>

              <div>
                <strong>Learning Materials</strong>
                <small>Open your uploaded PDFs and slides</small>
              </div>

              <span className="material-symbols-outlined">
                chevron_right
              </span>
            </div>

            <div
              className="plan-item clickable"
              onClick={() => setActivePage("tutor")}
            >
              <span className="material-symbols-outlined blue-text">
                smart_toy
              </span>

              <div>
                <strong>Ask AI Tutor</strong>
                <small>Ask questions about your study material</small>
              </div>

              <span className="material-symbols-outlined">
                chevron_right
              </span>
            </div>

            <div
              className="plan-item clickable"
              onClick={() => setActivePage("quiz")}
            >
              <span className="material-symbols-outlined green-text">
                psychology
              </span>

              <div>
                <strong>Adaptive Quiz</strong>
                <small>Practice topics and assess understanding</small>
              </div>

              <span className="material-symbols-outlined">
                chevron_right
              </span>
            </div>
          </div>

          <p className="dashboard-note">
            Study duration and document-reading progress are not
            yet tracked by the dashboard API.
          </p>
        </div>
      </section>
    </main>
  );
}


/* =========================================================
   MAIN APP
   ========================================================= */

function App() {
  const [activePage, setActivePage] = useState("analyzer");
  const [quizMaterial, setQuizMaterial] = useState(null);

  const navItems = [
    { id: "analyzer", icon: "description", label: "Resume Analyzer" },
    { id: "ats", icon: "fact_check", label: "ATS Checker" },
    { id: "matcher", icon: "work", label: "Job Matcher" },
    { id: "builder", icon: "edit_document", label: "Resume Builder" },
    { id: "history", icon: "history", label: "Analysis History" },
    { id: "documents", icon: "library_books", label: "Chat with Documents" },
  ];

  function renderPage() {
    if (activePage === "documents") return <>
      <main className="career-page">
        <header className="ci-page-title">
          <div>
            <h1>Chat with Documents</h1>
            <p className="ci-intro">Upload a PDF or presentation, ask questions, and follow citations back to the source pages. Conversations are saved in this browser.</p>
          </div>
        </header>
      </main>
      <TutorPage />
    </>;
    if (["analyzer", "ats", "matcher", "builder", "history"].includes(activePage)) {
      return <ResumeAnalyzer page={activePage} setActivePage={setActivePage} />;
    }
    switch (activePage) {
      case "tutor":
        return <TutorPage />;

      case "materials":
        return (
          <MaterialsPage
            setActivePage={setActivePage}
            onTakeQuiz={(material) => {
              setQuizMaterial(material);
              setActivePage("quiz");
            }}
          />
        );

      case "quiz":
        return (
          <AdaptiveQuiz
            material={quizMaterial}
            onQuizComplete={() => setActivePage("analytics")}
          />
        );
      case "analytics":
        return (
          <AnalyticsPage
            setActivePage={setActivePage}
          />
        );
      case "study-plan":
  return (
    <div className="simple-page">
      <h1>AI Study Plan</h1>
      <p>This page is currently unavailable.</p>
    </div>
  );

      case "settings":
        return <SettingsPage />;

      case "dashboard":
      default:
        return <DashboardPage setActivePage={setActivePage} />;
    }
  }
  return (
    <div className="app-shell">

      {/* SIDEBAR */}

      <aside className="sidebar">

        <div className="sidebar-content">

          {/* BRAND */}

          <div className="brand">

            <div className="brand-logo">
              🧠
            </div>

            <div>

              <div className="brand-name">

                Synapse

                <span>Career AI</span>

              </div>

              <div className="brand-subtitle">
                Resume & Career Intelligence
             </div>

            </div>

          </div>

          {/* COURSE */}
{/* 
          <div className="course-box">

            <span className="material-symbols-outlined course-symbol">
              school
            </span>

            <div>

              <p>
                Current Course
              </p>

              <strong>
                CS 201: Data Structures
              </strong>

            </div>

            <span className="material-symbols-outlined">
              expand_more
            </span>

          </div> */}

          {/* NAVIGATION */}

          <nav className="nav">

            {navItems.map(
              (item) => (

                <button
                  key={item.id}
                  className={`nav-item ${activePage ===
                    item.id
                    ? "active"
                    : ""
                    }`}
                  onClick={() =>
                    setActivePage(
                      item.id
                    )
                  }
                >

                  <span className="material-symbols-outlined">
                    {item.icon}
                  </span>

                  {item.label}

                </button>

              )
            )}

          </nav>

        </div>

      </aside>

      {/* MAIN AREA */}

      <div className="main-area">

        {/* TOPBAR */}

        {/* PAGE */}

        {renderPage()}

      </div>

    </div>
  );
}
export default App;
