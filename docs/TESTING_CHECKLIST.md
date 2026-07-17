# 🧪 Testing Checklist - Phase 1 Grading System

## ✅ What to Test

### 1. **Teacher: Grade Assignment Submissions**

#### Text/File Assignments
- [ ] Go to `/teacher/course/<id>/section/<id>/submissions`
- [ ] Click "Review" on a text or file submission
- [ ] Verify modal shows:
  - [ ] Student's text submission displayed
  - [ ] Uploaded file link (if file was uploaded)
  - [ ] Grade input field (0-100)
  - [ ] Feedback textarea
- [ ] Enter a grade (e.g., 85) and feedback
- [ ] Click "💾 Save Grade & Feedback"
- [ ] Verify success alert appears
- [ ] Verify table row shows "✓ Reviewed (85%)" in green

#### Code Assignments (Bug Fix Test)
- [ ] Create a coding assignment (check "This is a coding assignment")
- [ ] As student, submit code via editor (not file upload)
- [ ] As teacher, go to submissions page
- [ ] Verify "File" column shows "💻 Code Editor" (not "None")
- [ ] Click "Review"
- [ ] **BUG FIX VERIFIED**: Code displays in dark syntax box
- [ ] Verify language label shows (e.g., "Language: python")
- [ ] Grade the code submission
- [ ] Verify it saves successfully

### 2. **Student: View Grades**

#### Graded Assignment Display
- [ ] As student, go to course page
- [ ] Open a section with a graded assignment
- [ ] Verify grade card displays:
  - [ ] Large percentage number (e.g., 85%)
  - [ ] Progress bar filled to correct percentage
  - [ ] Green background if ≥70%
  - [ ] Yellow background if 50-69%
  - [ ] Red background if <50%
  - [ ] Teacher feedback below grade
  - [ ] "📝 Teacher Feedback:" label

#### Ungraded Assignment Display
- [ ] Open a section with reviewed but ungraded assignment
- [ ] Verify card shows:
  - [ ] Blue background (no grade)
  - [ ] Only feedback text
  - [ ] "No written feedback provided" if no feedback

#### Pending Review
- [ ] Submit a new assignment
- [ ] Verify shows "⏳ Awaiting review..." with spinning icon

### 3. **Edge Cases**

#### Grade Validation
- [ ] Try to enter grade > 100
- [ ] Verify alert: "Grade must be between 0 and 100"
- [ ] Try to enter grade < 0
- [ ] Verify same alert
- [ ] Try to enter decimal (e.g., 85.5)
- [ ] Verify it accepts and displays correctly

#### No Grade, Only Feedback
- [ ] Leave grade field empty
- [ ] Enter only feedback text
- [ ] Save
- [ ] Verify student sees feedback but no grade percentage

#### Update Existing Grade
- [ ] Review an already-graded submission
- [ ] Verify current grade shows in input field
- [ ] Change grade from 85 to 90
- [ ] Save
- [ ] Verify student sees updated grade

### 4. **Quiz Grading (Last Attempt Policy)**

Note: This is policy-only (for future gradebook). Currently:
- [ ] Student takes quiz 3 times
- [ ] Scores: 60%, 80%, 70%
- [ ] Verify "Best Score: 80%" displays
- [ ] **Policy**: Last attempt (70%) counts for final grade
- [ ] (Will be used when Phase 2 gradebook calculates overall grade)

---

## 🐛 Known Issues (Safe to Ignore)

### Linter Warnings
These are **false positives** from IDE parsing Jinja2 templates:
- `view_submissions.html` line 61: JavaScript linter errors
- `course_detail.html` line 48: CSS linter errors
- **All code works correctly at runtime** ✅

### Why They Occur
- Jinja2 syntax `{{ variable }}` inside JavaScript/CSS confuses the linter
- Can be fixed by refactoring to data attributes, but not necessary

---

## 📸 Expected Screenshots

### Teacher View - Submissions Table
```
+-------------+------------+------------+---------------+-------------------------+---------+
| Student Name| Assignment | Submitted  | File          | Status & Grade          | Actions |
+-------------+------------+------------+---------------+-------------------------+---------+
| John Doe    | Essay      | 2025-10-18 | View File     | ✓ Reviewed (85%)        | Review  |
| Jane Smith  | Code Lab   | 2025-10-17 | 💻 Code Editor| ⏳ Pending              | Review  |
+-------------+------------+------------+---------------+-------------------------+---------+
```

### Teacher View - Review Modal
```
+----------------------------------------------------------+
| 📝 Review Submission                                  [×] |
+----------------------------------------------------------+
| Student Submission:                                      |
| +------------------------------------------------------+ |
| | [Dark code box with syntax highlighting]             | |
| | Language: python                                     | |
| +------------------------------------------------------+ |
|                                                          |
| Grade (0-100%):                                          |
| [85__________]                                           |
| Leave empty if not grading numerically                   |
|                                                          |
| Written Feedback:                                        |
| [Great work! Your solution is efficient...]              |
|                                                          |
| [💾 Save Grade & Feedback]                               |
+----------------------------------------------------------+
```

### Student View - Graded Assignment
```
+----------------------------------------------------------+
| 📝 Assignment: Python Challenge                          |
+----------------------------------------------------------+
| [Submit button or "Submitted: 2025-10-18"]               |
|                                                          |
| +------------------------------------------------------+ |
| | Your Grade:                            85%         | | [Green background]
| | ████████████████████████████░░░░░░░░░░░░░░░░░░░░░ | |
| |                                                    | |
| | 📝 Teacher Feedback:                               | |
| | Great work! Your solution is efficient and clean.  | |
| +------------------------------------------------------+ |
+----------------------------------------------------------+
```

---

## ✅ Success Criteria

All features working if:
1. ✅ Teachers can see and grade code submissions
2. ✅ Grades save with validation (0-100)
3. ✅ Students see grades as large percentage with progress bar
4. ✅ Color coding works (green/yellow/red)
5. ✅ Feedback displays alongside grades
6. ✅ Table shows status with grade percentage
7. ✅ No CSRF errors when saving feedback

---

## 🚀 Quick Test Commands

```bash
# Restart Flask to load changes
cd /Users/dam1mac89/Desktop/pace
source .venv/bin/activate
python3 run.py

# Test URLs (replace <id> with actual IDs):
# Teacher submissions: http://127.0.0.1:5000/teacher/course/88/section/71/submissions
# Student course view: http://127.0.0.1:5000/student/course/88
```

---

**Test everything and let me know if anything doesn't work!** 🎉
