# Course Creation Wizard - Teacher vs Deployment Branch Analysis

## Current Status
Both branches have issues with the course creation wizard. The deployment branch is the "working" version but has the same structural problems.

## Key Differences: Teacher Branch Has EXTRA Features

### 1. **Additional Files in Teacher Branch**
- `app/static/js/quill-enhanced.js` - Enhanced Quill editor with H5P, tables, emojis
- `app/static/css/quill-buttons.css` - Custom Quill button styles
- `app/static/js/upload-progress.js` - Upload progress indicators
- Multiple new templates (base_teacher.html, base_student.html, calendar.html, etc.)

### 2. **Model Differences**
Teacher branch has:
- `User.profile_image` field (deployment doesn't have this)
- Enhanced Quiz model with `time_limit`, `passing_score`, `max_attempts`, `randomize_questions`, `show_correct_answers`
- QuizAttempt has `time_taken` and `completed_at` fields

### 3. **Route Differences**
Teacher branch has additional routes:
- `/teacher/media/<filename>` - Serve uploaded media
- `/teacher/course/<id>/delete-draft` - Delete draft courses
- `/teacher/profile` - Enhanced profile management
- Student routes have announcements, assignments, certificates, notifications

## The ACTUAL Problem with create_course_wizard.html

### Issue 1: Duplicate `setupTemplateSelection()` Function
**Both branches have this issue!**

Line 425: First call in DOMContentLoaded
Line 529-648: First definition (doesn't use Quill)
Line 697-805: Second definition (overrides first, uses Quill)
Line 808: Second call

**Problem:** Event listeners are attached twice, causing conflicts

### Issue 2: Quill Editor Complexity
**Both branches use Quill with the same pattern**

The deployment branch has:
- Quill editor initialization (line 673)
- Hidden textarea sync (line 689-691)
- Template selection override (line 697-805)

**Problem:** Quill adds unnecessary complexity for a simple description field

### Issue 3: Form Submission Error `[object RadioNodeList]`
This error suggests a form element is being read incorrectly. Likely causes:
- The `status` radio buttons (line 319-325) might be accessed incorrectly
- JavaScript might be trying to submit `form.status` instead of `form.status.value`

## Recommended Fix

### Option 1: Copy Deployment Exactly (Safest)
Just use the deployment version as-is since it "works"

### Option 2: Simplify Both (Best Long-term)
1. Remove Quill entirely - use simple textarea
2. Remove duplicate `setupTemplateSelection()` 
3. Fix any form submission issues
4. Keep only ONE definition of template selection

### Option 3: Fix Teacher Branch Properly
1. Keep teacher branch enhancements (profile_image, quiz features, etc.)
2. Copy ONLY the create_course_wizard.html from deployment
3. Test thoroughly

## What Teacher Branch Should Keep
- Enhanced models (profile_image, quiz enhancements)
- New routes (media serving, profile, etc.)
- New templates (base_teacher, calendar, etc.)
- Upload progress JavaScript
- Quill enhanced features (for OTHER pages, not course creation)

## What Should Be Fixed
- create_course_wizard.html should be simplified
- Remove Quill from course creation (or fix it properly)
- Remove duplicate function definitions
- Fix form submission to handle radio buttons correctly
