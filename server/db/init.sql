-- Create database (if not exists)
CREATE DATABASE IF NOT EXISTS epfl_courses_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_general_ci;

-- Use this database
USE epfl_courses_db;

-- Courses table
CREATE TABLE IF NOT EXISTS courses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(512) NOT NULL,
  description TEXT
);

-- Tag types table
CREATE TABLE IF NOT EXISTS tag_types (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(512) UNIQUE NOT NULL
);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tag_type_id INT NOT NULL,
  name VARCHAR(512) NOT NULL,
  UNIQUE KEY unique_tag (tag_type_id, name),
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