# Teacher Branch vs Deployment Branch - Complete Differences

## Files/Features ONLY in Teacher Branch (Not in Deployment)

### New Files
1. `app/static/js/quill-enhanced.js` - Enhanced rich text editor
2. `app/static/css/quill-buttons.css` - Quill custom styles  
3. `app/static/js/upload-progress.js` - File upload progress bars
4. `app/templates/teacher/base_teacher.html` - Teacher base template
5. `app/templates/teacher/calendar.html` - Teacher calendar view
6. `app/templates/teacher/course_calendar.html` - Course-specific calendar
7. `app/templates/teacher/view_as_student.html` - Preview as student
8. `app/templates/student/base_student.html` - Student base template
9. `app/templates/student/announcements.html` - Student announcements
10. `app/templates/student/assignments.html` - Student assignments view
11. `app/templates/student/calendar.html` - Student calendar
12. `app/templates/student/certificates.html` - Student certificates
13. `app/templates/student/help.html` - Student help page
14. `app/templates/student/notifications.html` - Student notifications
15. `migrations/add_quiz_enhancements.sql` - Quiz feature migrations
16. `migrations/add_quiz_time_limits.py` - Quiz timing migrations
17. `migrations/add_profile_image_to_users.py` - Profile image migration

### Database Model Enhancements
1. **User model** - Added `profile_image` field
2. **Quiz model** - Added:
   - `time_limit` (minutes)
   - `passing_score` (percentage)
   - `max_attempts` (integer)
   - `randomize_questions` (boolean)
   - `show_correct_answers` (boolean)
3. **QuizAttempt model** - Added:
   - `time_taken` (seconds)
   - `completed_at` (datetime)

### Route Enhancements
1. **Teacher routes** - Added:
   - `/teacher/media/<filename>` - Serve media files
   - `/teacher/course/<id>/delete-draft` - Delete draft courses
   - `/teacher/profile` - Enhanced profile with image upload
   - Calendar and course calendar views
   
2. **Student routes** - Enhanced:
   - Announcements viewing
   - Assignment submissions
   - Certificate downloads
   - Notification system
   - Help/support page

### Template Improvements
1. **Dashboard redesigns** - Both teacher and student dashboards improved
2. **Profile pages** - Enhanced with image upload
3. **Quiz/Assignment pages** - Better UI and functionality
4. **Responsive improvements** - Better mobile support

## The Core Problem with create_course_wizard.html

### BOTH Branches Have These Issues:
1. ❌ Duplicate `setupTemplateSelection()` function (called twice, defined twice)
2. ❌ Quill editor adds complexity
3. ❌ Form has no action attribute (submits to current URL)
4. ❌ Potential radio button handling issue with `status` field

### The `[object RadioNodeList]` Error
**Root Cause:** When JavaScript accesses `form.status`, it returns a RadioNodeList object instead of the selected value.

**Where it happens:** Likely in the autosave or form submission JavaScript

**Fix needed:** Use `form.status.value` or `document.querySelector('input[name="status"]:checked').value`

## Recommendation

### Immediate Fix (Choose One):

#### Option A: Use Pure Deployment Version
```bash
# Discard all teacher changes to this file
git checkout deployment -- app/templates/teacher/create_course_wizard.html
git commit -m "Use working deployment version of course wizard"
```

#### Option B: Simplify Teacher Version  
1. Remove Quill editor completely
2. Remove duplicate setupTemplateSelection
3. Use simple textarea
4. Fix radio button access in JavaScript

#### Option C: Fix Form Action
Add explicit form action:
```html
<form method="POST" action="{{ url_for('teacher.create_course_wizard', step=current_step) }}" ...>
```

## My Recommendation: Option A
Just use the deployment version since it works. The teacher branch's enhancements (profile images, quiz features, etc.) are in OTHER files and won't be affected.

The course creation wizard doesn't need the fancy features - it just needs to work reliably.
