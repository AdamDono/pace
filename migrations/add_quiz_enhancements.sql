-- Database Migration: Quiz Enhancements (PostgreSQL)
-- Add time limits and additional settings to quizzes
-- Database: paceacademy (PostgreSQL on localhost:5433)

-- ⚠️  WARNING: DO NOT RUN THIS FILE DIRECTLY!
-- Use the Python migration script instead: python3 migrations/add_quiz_time_limits.py

-- This file is kept for reference only

-- Add new columns to Quiz table
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS time_limit INTEGER;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS passing_score FLOAT DEFAULT 60.0;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS max_attempts INTEGER;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS randomize_questions BOOLEAN DEFAULT FALSE;
ALTER TABLE quizzes ADD COLUMN IF NOT EXISTS show_correct_answers BOOLEAN DEFAULT TRUE;

-- Add new columns to QuizAttempt table
ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS time_taken INTEGER;
ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;

-- Update existing quizzes with default values
UPDATE quizzes SET passing_score = 60.0 WHERE passing_score IS NULL;
UPDATE quizzes SET randomize_questions = FALSE WHERE randomize_questions IS NULL;
UPDATE quizzes SET show_correct_answers = TRUE WHERE show_correct_answers IS NULL;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_quiz_time_limit ON quizzes(time_limit);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student ON quiz_attempts(student_id, quiz_id);
