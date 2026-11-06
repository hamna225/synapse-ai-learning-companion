import json

import main


class FakeResponse:
    def __init__(self, content):
        self.content = content


class TopicModel:
    def invoke(self, prompt):
        if "TOPIC CANDIDATES:" in prompt:
            candidates = json.loads(prompt.split("TOPIC CANDIDATES:", 1)[1])
            return FakeResponse(json.dumps({"topics": candidates}))
        if "portion 1 of 2" in prompt:
            topics = [{"topic": "Topic Alpha", "subtopics": ["Alpha concepts"]}]
        elif "portion 2 of 2" in prompt:
            topics = [{"topic": "Topic Beta", "subtopics": ["Beta concepts"]}]
        else:
            raise AssertionError("Expected the full document to be split into two batches")
        return FakeResponse(json.dumps({"topics": topics}))


class FakeVectorStore:
    def get(self, include):
        assert include == ["documents", "metadatas"]
        return {
            "documents": ["alpha " + "a" * 16000, "beta " + "b" * 16000],
            "metadatas": [{"page": 1}, {"page": 2}],
        }


class FakeRetriever:
    vectorstore = FakeVectorStore()


def test_topics_scans_all_document_batches_and_merges_without_api(monkeypatch):
    monkeypatch.setattr(main, "get_groq_text_model", lambda **kwargs: TopicModel())
    monkeypatch.setattr(main, "get_retriever", lambda material_id: FakeRetriever())

    result = main.get_topics(main.TopicsRequest(material_id="material-test"))

    assert [topic["topic"] for topic in result["topics"]] == ["Topic Alpha", "Topic Beta"]


def test_document_qa_returns_grounded_answer_and_source_citation(monkeypatch):
    class AnswerModel:
        def invoke(self, prompt):
            assert "[1] (Page 4)" in prompt
            return FakeResponse("Python is used for data analysis [1].")

    class Doc:
        page_content = "Python supports data analysis."
        metadata = {"page": 4}

    class Retriever:
        def invoke(self, question):
            assert question == "What is Python used for?"
            return [Doc()]

    monkeypatch.setattr(main, "get_groq_text_model", lambda **kwargs: AnswerModel())
    monkeypatch.setattr(main, "get_retriever", lambda material_id: Retriever())

    result = main.ask_question(main.AskRequest(material_id="material-test", question="What is Python used for?"))

    assert result["answer"] == "Python is used for data analysis [1]."
