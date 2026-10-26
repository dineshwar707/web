CREATE DATABASE IF NOT EXISTS online_exam1
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE online_exam1;

CREATE TABLE IF NOT EXISTS portal_students (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    dob DATE NOT NULL,
    age TINYINT UNSIGNED NULL,
    gender ENUM('male', 'female', 'other') NOT NULL,
    course VARCHAR(20) NOT NULL,
    photo_path VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_registrations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    roll_no VARCHAR(30) NOT NULL,
    enrollment VARCHAR(50) NOT NULL,
    student_name VARCHAR(100) NOT NULL,
    program VARCHAR(150) NOT NULL,
    semester TINYINT UNSIGNED NOT NULL,
    exam_session VARCHAR(100) NOT NULL,
    exam_mode VARCHAR(50) NOT NULL,
    exam_center VARCHAR(150) NOT NULL,
    emergency_phone VARCHAR(20) NOT NULL,
    scribe_needed BOOLEAN NOT NULL DEFAULT FALSE,
    ground_floor BOOLEAN NOT NULL DEFAULT FALSE,
    extra_time BOOLEAN NOT NULL DEFAULT FALSE,
    payment_method ENUM('card', 'upi', 'netbanking', 'wallet') NOT NULL,
    paper_details LONGTEXT NOT NULL,
    total_fee DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_exam_registration (roll_no, semester, exam_session)
);
