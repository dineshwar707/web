import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SESSION_SECRET", "test-session-secret-that-is-long-enough")

import app as backend


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.client = backend.app.test_client()
        self.connection_patch = patch("app.get_connection")
        self.get_connection = self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)

    def test_home_page_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SRTD University", response.data)
        response.close()

    def test_api_me_requires_a_valid_session(self):
        response = self.client.get("/api/me")
        self.assertEqual(response.status_code, 401)
        self.assertIn("portal_session=", response.headers["Set-Cookie"])

    def test_login_uses_existing_scrypt_hash_format(self):
        student = {
            "id": 17,
            "first_name": "Test",
            "last_name": "Student",
            "email": "test@example.com",
            "password_hash": backend.hash_password("correct-password"),
            "course": "btech",
        }
        cursor = self.get_connection.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = student

        response = self.client.post(
            "/api/login",
            data={"student_id": "TEST@example.com", "login_pwd": "correct-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("portal_session=", response.headers["Set-Cookie"])
        self.assertEqual(response.get_json()["student"]["id"], 17)

    def test_registration_validates_before_database_access(self):
        response = self.client.post(
            "/api/register",
            data={
                "fname": "First",
                "lname": "Last",
                "email": "invalid",
                "password": "correct-password",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.get_connection.assert_not_called()

    def test_registration_saves_photo_and_creates_student(self):
        cursor = self.get_connection.return_value.cursor.return_value.__enter__.return_value
        cursor.lastrowid = 31
        with tempfile.TemporaryDirectory() as upload_directory:
            with patch.object(backend, "UPLOAD_DIRECTORY", Path(upload_directory)):
                response = self.client.post(
                    "/api/register",
                    data={
                        "fname": "Test",
                        "lname": "Student",
                        "email": "test@example.com",
                        "password": "correct-password",
                        "dob": "2000-01-02",
                        "age": "26",
                        "gender": "other",
                        "course": "btech",
                        "terms": "on",
                        "photo": (BytesIO(b"test image data"), "student.png", "image/png"),
                    },
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.get_json()["student"]["id"], 31)
                saved_photos = list(Path(upload_directory).glob("*.png"))
                self.assertEqual(len(saved_photos), 1)
                cursor.execute.assert_called_once()
                self.get_connection.return_value.commit.assert_called_once()

    def test_exam_registration_saves_selected_papers_and_server_fee(self):
        cursor = self.get_connection.return_value.cursor.return_value.__enter__.return_value
        cursor.lastrowid = 42
        response = self.client.post(
            "/api/exam-registrations",
            json={
                "roll_no": "24CS1044",
                "enrollment": "SRTD-2024-8932",
                "student_name": "Test Student",
                "program": "B.Tech - Computer Science & Engineering",
                "semester": "4",
                "exam_session": "Nov-Dec 2026 Regular",
                "exam_mode": "Physical Pen & Paper",
                "exam_center": "SRTD University Main Campus - Academic Block A",
                "emergency_phone": "+91 98765 43210",
                "payment_method": "card",
                "declaration": True,
                "subject_codes": ["CS401", "CS403L"],
                "elective_code": "CS405",
                "backlog_codes": [],
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["registration_id"], 42)
        self.assertEqual(response.get_json()["total_fee"], 2250)
        self.assertEqual(cursor.execute.call_count, 1)
        inserted_values = cursor.execute.call_args.args[1]
        self.assertEqual(inserted_values[0], "24CS1044")
        self.assertEqual(inserted_values[-1], 2250)
        self.get_connection.return_value.commit.assert_called_once()

    def test_exam_registration_rejects_invalid_paper_without_database_access(self):
        response = self.client.post(
            "/api/exam-registrations",
            json={
                "roll_no": "24CS1044",
                "enrollment": "SRTD-2024-8932",
                "student_name": "Test Student",
                "program": "B.Tech - Computer Science & Engineering",
                "semester": "4",
                "exam_session": "Nov-Dec 2026 Regular",
                "exam_mode": "Physical Pen & Paper",
                "exam_center": "SRTD University Main Campus - Academic Block A",
                "emergency_phone": "+91 98765 43210",
                "payment_method": "card",
                "declaration": True,
                "subject_codes": ["NOT-A-SEMESTER-4-PAPER"],
                "elective_code": "CS405",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.get_connection.assert_not_called()

    def test_session_cookie_signature_is_verified(self):
        cookie = backend.create_session_cookie_value(23, 9_999_999_999_999)
        self.assertEqual(backend.get_session_student_id(cookie), "23")
        self.assertIsNone(backend.get_session_student_id(cookie + "tampered"))


if __name__ == "__main__":
    unittest.main()
