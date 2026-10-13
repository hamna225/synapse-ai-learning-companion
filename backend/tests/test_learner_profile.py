from student_analytics import learner_profile


def test_adaptive_difficulty_uses_prior_mastery():
    choose = learner_profile.choose_starting_difficulty
    assert choose(0, 0.2) == "medium"
    assert choose(5, 0.3) == "easy"
    assert choose(5, 0.6) == "medium"
    assert choose(5, 0.85) == "hard"


def test_bkt_mastery_updates_and_persists_between_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(
        learner_profile,
        "PROFILE_PATH",
        tmp_path / "learner_state.json",
    )

    first = learner_profile.record_answer(
        topic="Machine Learning",
        subtopic="Supervised Learning",
        is_correct=True,
        quiz_id="quiz-one",
        material_id="material-one",
        difficulty="medium",
        question_number=1,
        total_questions=2,
    )
    second = learner_profile.record_answer(
        topic="Machine Learning",
        subtopic="Supervised Learning",
        is_correct=False,
        quiz_id="quiz-one",
        material_id="material-one",
        difficulty="hard",
        question_number=2,
        total_questions=2,
    )

    profile = learner_profile.load_profile()
    assert first["topic_mastery"] > 20
    assert second["topic_mastery"] < first["topic_mastery"]
    assert profile["topics"]["Machine Learning"]["total"] == 2
    assert profile["overview"]["questions_answered"] == 2

    learner_profile.complete_quiz("quiz-one")
    learner_profile.complete_quiz("quiz-one")
    profile = learner_profile.load_profile()
    assert profile["overview"]["completed_quizzes"] == 1
    assert profile["recent_activity"][0]["completed"] is True
