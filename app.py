import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from db import get_connection, initialize_database

load_dotenv()

BASE_DIRECTORY = Path(__file__).resolve().parent
PUBLIC_DIRECTORY = BASE_DIRECTORY / "public"
UPLOAD_DIRECTORY = BASE_DIRECTORY / "uploads"
SESSION_COOKIE_NAME = "portal_session"
SESSION_DURATION_SECONDS = 60 * 60 * 24
COURSES = {"btech", "bba", "bsc", "mca"}
GENDERS = {"male", "female", "other"}
PHOTO_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EXAM_SUBJECT_FEES = {
    "1": {"MA101": 650, "PH101": 650, "CS101": 650, "EE101": 500, "CS101L": 500},
    "2": {"MA102": 650, "CS201": 650, "CS202": 650, "EC201": 500, "CS201L": 500},
    "3": {"CS301": 650, "CS302": 650, "CS303": 650, "MA301": 500, "CS301L": 500},
    "4": {"CS401": 650, "CS402": 650, "CS403": 650, "CS404": 650, "CS403L": 500},
    "5": {"CS501": 650, "CS502": 650, "CS503": 650, "CS501L": 500},
    "6": {"CS601": 650, "CS602": 650, "CS603": 650, "CS603L": 500},
}
EXAM_ELECTIVES = {
    "CS405": "Artificial Intelligence & Neural Nets",
    "CS406": "Cloud Computing & DevOps Architecture",
    "CS407": "Cyber Security & Cryptography",
}
EXAM_BACKLOGS = {
    "MA101": "Engineering Mathematics I (Sem 1)",
    "PH101": "Applied Physics (Sem 1)",
    "CS202": "Discrete Mathematics (Sem 2)",
}
EXAM_SESSIONS = {"Nov-Dec 2026 Regular", "Jan 2027 Supplementary"}
EXAM_MODES = {"Physical Pen & Paper", "Online Proctored Lab"}
EXAM_CENTERS = {
    "SRTD University Main Campus - Academic Block A",
    "SRTD North Campus Auditorium Hall",
    "SRTD City Centre - Examination Center",
}
PAYMENT_METHODS = {"card", "upi", "netbanking", "wallet"}
PHONE_PATTERN = re.compile(r"^(?:\+91[-\s]?)?[6-9]\d{4}[-\s]?\d{5}$")


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify(message="The uploaded photo must be 5 MB or smaller."), 413

    @app.get("/")
    def index():
        return send_from_directory(PUBLIC_DIRECTORY, "index.html")

    @app.get("/<path:filename>")
    def public_file(filename):
        return send_from_directory(PUBLIC_DIRECTORY, filename)

    @app.post("/api/register")
    def register():
        first_name = request.form.get("fname", "").strip()
        last_name = request.form.get("lname", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        dob = request.form.get("dob", "")
        age_text = request.form.get("age", "")
        gender = request.form.get("gender", "")
        course = request.form.get("course", "")

        if not first_name or len(first_name) > 50 or not last_name or len(last_name) > 50:
            return jsonify(message="Enter a first name and last name (up to 50 characters each)."), 400
        if not EMAIL_PATTERN.fullmatch(email) or len(email) > 254:
            return jsonify(message="Enter a valid email address."), 400
        if not 8 <= len(password) <= 128:
            return jsonify(message="Password must be between 8 and 128 characters."), 400
        try:
            parsed_dob = date.fromisoformat(dob)
            if parsed_dob.isoformat() != dob:
                raise ValueError
        except ValueError:
            return jsonify(message="Enter a valid date of birth."), 400

        age = None
        if age_text:
            try:
                age = int(age_text)
            except ValueError:
                return jsonify(message="Age must be between 16 and 100."), 400
            if not 16 <= age <= 100:
                return jsonify(message="Age must be between 16 and 100."), 400
        if gender not in GENDERS or course not in COURSES:
            return jsonify(message="Select a valid gender and program."), 400
        if request.form.get("terms") != "on":
            return jsonify(message="Accept the terms and conditions to continue."), 400

        photo = request.files.get("photo")
        extension = PHOTO_EXTENSIONS.get(photo.mimetype if photo else "")
        if not photo or not photo.filename or not extension:
            return jsonify(message="Upload a JPG, PNG, or WEBP passport photo."), 400
        photo_data = photo.stream.read(5 * 1024 * 1024 + 1)
        if len(photo_data) > 5 * 1024 * 1024:
            return jsonify(message="The uploaded photo must be 5 MB or smaller."), 413

        UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        photo_name = f"{uuid.uuid4()}{extension}"
        photo_path = UPLOAD_DIRECTORY / secure_filename(photo_name)
        photo_path.write_bytes(photo_data)

        connection = None
        try:
            password_hash = hash_password(password)
            connection = get_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO portal_students
                       (first_name, last_name, email, password_hash, dob, age, gender, course, photo_path)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        first_name,
                        last_name,
                        email,
                        password_hash,
                        dob,
                        age,
                        gender,
                        course,
                        photo_name,
                    ),
                )
                student_id = cursor.lastrowid
            connection.commit()
            return jsonify(
                message="Registration successful. You can now log in.",
                student={
                    "id": student_id,
                    "firstName": first_name,
                    "lastName": last_name,
                    "email": email,
                    "course": course,
                },
            ), 201
        except Exception as error:
            if connection:
                connection.rollback()
            try:
                photo_path.unlink(missing_ok=True)
            except OSError:
                app.logger.exception("Unable to remove an unused student photo")
            if getattr(error, "errno", None) == 1062:
                return jsonify(message="An account already exists for this email address."), 409
            app.logger.exception("Student registration failed")
            return jsonify(message="Registration could not be completed. Please try again."), 500
        finally:
            if connection:
                connection.close()

    @app.post("/api/login")
    def login():
        data = request.get_json() if request.is_json else request.form
        email = str(data.get("student_id", "")).strip().lower()
        password = str(data.get("login_pwd", ""))
        if not email or not password:
            return jsonify(message="Enter your email address and password."), 400

        connection = None
        try:
            connection = get_connection()
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """SELECT id, first_name, last_name, email, password_hash, course
                       FROM portal_students WHERE email = %s LIMIT 1""",
                    (email,),
                )
                student = cursor.fetchone()
            if not student or not verify_password(password, student["password_hash"]):
                return jsonify(message="Email address or password is incorrect."), 401

            response = make_response(
                jsonify(message="Login successful.", student=public_student(student))
            )
            set_session_cookie(response, student["id"])
            return response
        except Exception:
            app.logger.exception("Student login failed")
            return jsonify(message="Login could not be completed. Please try again."), 500
        finally:
            if connection:
                connection.close()

    @app.post("/api/exam-registrations")
    def exam_registration():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(message="Invalid registration request."), 400

        roll_no = str(data.get("roll_no", "")).strip()
        enrollment = str(data.get("enrollment", "")).strip()
        student_name = str(data.get("student_name", "")).strip()
        program = str(data.get("program", "")).strip()
        semester = str(data.get("semester", "")).strip()
        exam_session = str(data.get("exam_session", "")).strip()
        exam_mode = str(data.get("exam_mode", "")).strip()
        exam_center = str(data.get("exam_center", "")).strip()
        emergency_phone = str(data.get("emergency_phone", "")).strip()
        payment_method = str(data.get("payment_method", "")).strip()

        if (
            not roll_no or len(roll_no) > 30
            or not enrollment or len(enrollment) > 50
            or not student_name or len(student_name) > 100
            or not program or len(program) > 150
        ):
            return jsonify(message="Enter valid candidate and enrollment details."), 400
        if semester not in EXAM_SUBJECT_FEES:
            return jsonify(message="Select a valid examination semester."), 400
        if exam_session not in EXAM_SESSIONS or exam_mode not in EXAM_MODES:
            return jsonify(message="Select a valid examination session and mode."), 400
        if exam_center not in EXAM_CENTERS:
            return jsonify(message="Select a valid examination center."), 400
        if not PHONE_PATTERN.fullmatch(emergency_phone):
            return jsonify(message="Enter a valid Indian mobile number."), 400
        if payment_method not in PAYMENT_METHODS:
            return jsonify(message="Select a valid payment method."), 400
        if data.get("declaration") is not True:
            return jsonify(message="Accept the declaration to continue."), 400
        accommodation_fields = ("scribe_needed", "ground_floor", "extra_time")
        if any(
            field in data and not isinstance(data[field], bool)
            for field in accommodation_fields
        ):
            return jsonify(message="Invalid accessibility selection."), 400

        selected_subjects = data.get("subject_codes")
        selected_backlogs = data.get("backlog_codes", [])
        elective_code = str(data.get("elective_code", "")).strip()
        if (
            not isinstance(selected_subjects, list)
            or not selected_subjects
            or any(not isinstance(code, str) for code in selected_subjects)
            or len(set(selected_subjects)) != len(selected_subjects)
        ):
            return jsonify(message="Select at least one valid examination paper."), 400
        if any(code not in EXAM_SUBJECT_FEES[semester] for code in selected_subjects):
            return jsonify(message="One or more selected papers are not valid for this semester."), 400
        if (
            not isinstance(selected_backlogs, list)
            or any(not isinstance(code, str) or code not in EXAM_BACKLOGS for code in selected_backlogs)
            or len(set(selected_backlogs)) != len(selected_backlogs)
        ):
            return jsonify(message="One or more selected backlog papers are invalid."), 400
        if elective_code not in EXAM_ELECTIVES:
            return jsonify(message="Select a valid elective paper."), 400

        regular_papers = [
            {"code": code, "fee": EXAM_SUBJECT_FEES[semester][code]}
            for code in selected_subjects
        ]
        backlog_papers = [
            {"code": code, "name": EXAM_BACKLOGS[code], "fee": 1000}
            for code in selected_backlogs
        ]
        elective_paper = {
            "code": elective_code,
            "name": EXAM_ELECTIVES[elective_code],
            "fee": 750,
        }
        total_fee = (
            sum(paper["fee"] for paper in regular_papers)
            + elective_paper["fee"]
            + sum(paper["fee"] for paper in backlog_papers)
            + 350
        )
        paper_details = json.dumps(
            {
                "regular": regular_papers,
                "elective": elective_paper,
                "backlog": backlog_papers,
            },
            separators=(",", ":"),
        )
        connection = None
        try:
            connection = get_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO exam_registrations
                       (roll_no, enrollment, student_name, program, semester, exam_session,
                        exam_mode, exam_center, emergency_phone, scribe_needed, ground_floor,
                        extra_time, payment_method, paper_details, total_fee)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        roll_no,
                        enrollment,
                        student_name,
                        program,
                        int(semester),
                        exam_session,
                        exam_mode,
                        exam_center,
                        emergency_phone,
                        bool(data.get("scribe_needed")),
                        bool(data.get("ground_floor")),
                        bool(data.get("extra_time")),
                        payment_method,
                        paper_details,
                        total_fee,
                    ),
                )
                registration_id = cursor.lastrowid
            connection.commit()
            return jsonify(
                message="Exam registration saved successfully.",
                registration_id=registration_id,
                total_fee=total_fee,
            ), 201
        except Exception as error:
            if connection:
                connection.rollback()
            if getattr(error, "errno", None) == 1062:
                return jsonify(message="This examination registration already exists."), 409
            app.logger.exception("Exam registration failed")
            return jsonify(message="Exam registration could not be saved. Please try again."), 500
        finally:
            if connection:
                connection.close()

    @app.get("/api/me")
    def current_student():
        student_id = get_session_student_id(request.cookies.get(SESSION_COOKIE_NAME, ""))
        if not student_id:
            response = make_response(jsonify(message="Please log in to continue."), 401)
            clear_session_cookie(response)
            return response

        connection = None
        try:
            connection = get_connection()
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    """SELECT id, first_name, last_name, email, course
                       FROM portal_students WHERE id = %s LIMIT 1""",
                    (student_id,),
                )
                student = cursor.fetchone()
            if not student:
                response = make_response(jsonify(message="Please log in to continue."), 401)
                clear_session_cookie(response)
                return response
            return jsonify(student=public_student(student))
        except Exception:
            app.logger.exception("Unable to load the student session")
            return jsonify(message="Unable to load your profile right now."), 500
        finally:
            if connection:
                connection.close()

    @app.post("/api/logout")
    def logout():
        response = make_response(jsonify(message="Logged out."))
        clear_session_cookie(response)
        return response

    return app


def hash_password(password):
    salt = secrets.token_hex(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("ascii"),
        n=16384,
        r=8,
        p=1,
        dklen=64,
    )
    return f"scrypt:{salt}:{derived_key.hex()}"


def verify_password(password, stored_hash):
    try:
        algorithm, salt, expected_hex = stored_hash.split(":")
        if algorithm != "scrypt" or not re.fullmatch(r"[a-fA-F0-9]{128}", expected_hex):
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt.encode("ascii"),
            n=16384,
            r=8,
            p=1,
            dklen=64,
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (ValueError, UnicodeError):
        return False


def create_session_cookie_value(student_id, expires_at):
    secret = os.environ.get("SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("SESSION_SECRET must be at least 32 characters long in the .env file.")
    payload = f"{student_id}.{expires_at}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def get_session_student_id(value):
    parts = value.split(".")
    if len(parts) != 3:
        return None
    student_id, expires_at_text, signature = parts
    if not student_id.isdigit() or not expires_at_text.isdigit():
        return None
    expires_at = int(expires_at_text)
    if expires_at > 9_007_199_254_740_991 or expires_at <= int(time.time() * 1000):
        return None
    try:
        expected = create_session_cookie_value(student_id, expires_at).rsplit(".", 1)[1]
    except RuntimeError:
        return None
    if not hmac.compare_digest(signature.lower(), expected):
        return None
    return student_id


def set_session_cookie(response, student_id):
    expires_at = int(time.time() * 1000) + SESSION_DURATION_SECONDS * 1000
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_cookie_value(student_id, expires_at),
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        secure=os.environ.get("NODE_ENV") == "production",
        samesite="Lax",
        path="/",
    )


def clear_session_cookie(response):
    response.set_cookie(
        SESSION_COOKIE_NAME,
        "",
        max_age=0,
        httponly=True,
        samesite="Lax",
        path="/",
    )


def public_student(student):
    return {
        "id": student["id"],
        "firstName": student["first_name"],
        "lastName": student["last_name"],
        "email": student["email"],
        "course": student["course"],
    }


app = create_app()


if __name__ == "__main__":
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    initialize_database()
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port)
