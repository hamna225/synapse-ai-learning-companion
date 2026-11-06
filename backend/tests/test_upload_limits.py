import pytest
from fastapi import HTTPException

import main


def _create_session(session_id, student_id):
    with main._upload_db_connection() as connection:
        connection.execute(
            "INSERT INTO learning_sessions (session_id, student_id) VALUES (?, ?)",
            (session_id, student_id),
        )


def test_pdf_upload_limit_is_five_per_student_profile(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "SYNAPSE_UPLOAD_DB_PATH",
        str(tmp_path / "upload_limits.sqlite3"),
    )
    monkeypatch.setenv("MAX_PDF_UPLOADS_PER_STUDENT", "5")
    _create_session("session-a", "student-a")
    _create_session("session-b", "student-b")

    for index in range(5):
        main._reserve_pdf_upload("session-a", f"material-{index}")
        main._finish_pdf_upload(f"material-{index}")

    with pytest.raises(HTTPException) as error:
        main._reserve_pdf_upload("session-a", "material-six")
    assert error.value.status_code == 429

    main._reserve_pdf_upload("session-b", "other-student-material")


def test_failed_pdf_upload_reservation_can_be_released(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "SYNAPSE_UPLOAD_DB_PATH",
        str(tmp_path / "upload_limits.sqlite3"),
    )
    monkeypatch.setenv("MAX_PDF_UPLOADS_PER_STUDENT", "1")
    _create_session("session-a", "student-a")

    main._reserve_pdf_upload("session-a", "failed-material")
    main._release_pdf_upload("failed-material")
    main._reserve_pdf_upload("session-a", "replacement-material")
