-- Create database (if not exists)
CREATE DATABASE IF NOT EXISTS epfl_courses_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_general_ci;

-- Use this database
USE epfl_courses_db;

CREATE TABLE IF NOT EXISTS courses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  course_name VARCHAR(512) NOT NULL,
  course_code VARCHAR(128) NOT NULL,
  course_url VARCHAR(1024),
  credits INT NOT NULL,
  lang VARCHAR(64) NOT NULL,
  semester VARCHAR(64) NOT NULL,
  exam_form VARCHAR(128),
  workload VARCHAR(128),
  UNIQUE KEY uniq_course_code (course_code)
);

-- Course offerings (section-level) table
CREATE TABLE IF NOT EXISTS course_offerings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  course_id INT NOT NULL,
  section VARCHAR(64) NOT NULL,
  type ENUM('mandatory', 'optional') NOT NULL,
  prof_name VARCHAR(512),
  UNIQUE KEY uniq_course_section (course_id, section),
  INDEX idx_offerings_course (course_id),
  INDEX idx_offerings_section (section),
  INDEX idx_offerings_type (type),
  FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- Backward-compatibility view (optional): exposes `url` as alias of `course_url`
DROP VIEW IF EXISTS courses_with_url;
CREATE VIEW courses_with_url AS
  SELECT id, course_name, course_code, course_url AS url, credits, lang, semester, exam_form, workload
  FROM courses;

-- Tag types table
CREATE TABLE IF NOT EXISTS tag_types (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(512) UNIQUE NOT NULL
);

-- Seed filter tag types
INSERT IGNORE INTO tag_types (name) VALUES
  ('keywords'),
  ('available_programs');

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tag_type_id INT NOT NULL,
  name VARCHAR(1024) NOT NULL,
  name_hash CHAR(64) GENERATED ALWAYS AS (SHA2(name, 256)) STORED,
  UNIQUE KEY unique_tag (tag_type_id, name_hash),
  FOREIGN KEY (tag_type_id) REFERENCES tag_types(id) ON DELETE CASCADE
);

-- Course and tag relationship table
CREATE TABLE IF NOT EXISTS course_tags (
  course_id INT NOT NULL,
  tag_id INT NOT NULL,
  PRIMARY KEY (course_id, tag_id),
  FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);