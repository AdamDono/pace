# 📝 Quill Editor & H5P Integration Guide

## ✨ Features Available

Your Pace Academy now has enhanced content creation with:
- **😀 Emoji Picker** - 60+ emojis
- **📊 Tables** - Insert and edit tables
- **🎮 H5P Interactive Content** - Quizzes, videos, games, and more
- **</> Source Code Editor** - Edit HTML directly with Monaco editor (syntax highlighting)

---

## 🎮 How to Use H5P

### What is H5P?
H5P lets you create interactive content like:
- Interactive videos with embedded questions
- Quizzes and assessments
- Drag-and-drop exercises
- Timelines
- Memory games
- Course presentations
- And 40+ more content types

### Step 1: Create H5P Account

**Option A: H5P.com (Easiest)**
1. Go to: https://h5p.com/free-trial
2. Sign up (free trial, no credit card needed)
3. Get instant access to create content

**Option B: H5P.org (100% Free Forever)**
1. Go to: https://h5p.org
2. Create free account
3. Unlimited content creation

### Step 2: Create Your Content

1. **Login** to H5P.com or H5P.org
2. **Click "Create"** or "Create new content"
3. **Choose content type**:
   - **Interactive Video** ⭐ (easiest - add questions to videos)
   - **Quiz (Question Set)** ⭐ (multiple choice, true/false)
   - **Course Presentation** (PowerPoint-like slides)
   - **Drag and Drop** (matching exercises)
   - **Timeline** (historical events)
   - **Memory Game** (flashcards)
4. **Build your content** using the editor
5. **Click "Save"**

### Step 3: Get Embed Code

**From H5P.com:**
1. After saving, click on your content
2. Click **"Embed"** button
3. Copy the URL or full iframe code
   ```
   https://YOUR-ACCOUNT.h5p.com/content/1234567890
   ```

**From H5P.org:**
1. After saving, click **"Reuse"** or **"Share"**
2. Copy the embed URL
   ```
   https://h5p.org/h5p/embed/XXXXX
   ```

### Step 4: Embed in Pace Academy

1. **Go to**: Course → Module → Edit Section
2. **Click the 🎮 H5P button** in the editor toolbar
3. **Paste** your H5P URL or full iframe code
4. **Click "Insert"**
5. **Save the section**
6. **Done!** Students can now interact with it

### Step 5: Edit Your H5P Content

**To edit existing content:**
1. Go back to **H5P.com** or **H5P.org**
2. **Login** to your account
3. Find your content in **"My Content"**
4. **Click "Edit"**
5. Make your changes
6. **Click "Save"**
7. **Changes appear automatically** in your app! ✨

**No need to re-embed!** The URL stays the same.

---

## 🎯 Quick Example: Interactive Video

### Create Your First Interactive Video:

1. **Go to H5P.com** and login
2. **Click "Create"** → Select **"Interactive Video"**
3. **Add a video**:
   - Paste YouTube URL (e.g., any educational video)
   - Or upload your own video
4. **Add interactions**:
   - Click timeline where you want a question
   - Choose interaction type (Multiple Choice, True/False, etc.)
   - Write your question and answers
   - Set correct answer
5. **Add more questions** at different timestamps
6. **Click "Save"**
7. **Copy the embed URL**
8. **Paste in Pace Academy 🎮 H5P modal**

**That's it!** Students will see the video with interactive questions.

---

## 😀 How to Use Emoji Picker

1. **Click the 😀 button** in the editor toolbar
2. **Modal opens** with 60+ emojis
3. **Click any emoji** to insert it at cursor position
4. **Done!**

---

## 📊 How to Use Tables

1. **Click the 📊 button** in the editor toolbar
2. **A 3x3 table appears** in the editor
3. **Edit cells**: Click and type
4. **Right-click cells** for options:
   - Insert row above/below
   - Insert column left/right
   - Delete row/column
   - Merge cells
   - Split cells
5. **Done!**

---

## </> How to Use Source Code Editor

### What is it?
The source code editor lets you edit the raw HTML of your content with:
- **Syntax highlighting** - Color-coded HTML for easy reading
- **Line numbers** - Navigate easily
- **Auto-complete** - Helps write valid HTML
- **Custom CSS** - Add inline styles and custom classes

### When to use it:
- **Advanced formatting** - Add custom HTML/CSS
- **Fix formatting issues** - Clean up messy HTML
- **Copy/paste HTML** - From other sources
- **Custom embeds** - Add widgets, calculators, etc.
- **Fine-tune layout** - Precise control over appearance

### How to use:

1. **Click the </> button** in the editor toolbar
2. **Monaco editor opens** in a modal with your current HTML
3. **Edit the HTML**:
   - Syntax highlighting makes it easy to read
   - Add custom `<div>`, `<span>`, inline styles
   - Add CSS classes: `class="my-custom-class"`
   - Add inline styles: `style="color: red; font-size: 20px;"`
4. **Click "Save"** to apply changes
5. **Click "Cancel"** to discard changes

### Example - Custom Styled Box:

**Visual Editor**: Limited styling options

**Source Code Editor**: Add this HTML:
```html
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 20px; 
            border-radius: 12px; 
            color: white; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);">
  <h3 style="margin: 0 0 10px 0;">💡 Pro Tip</h3>
  <p style="margin: 0;">This is a custom styled box with gradient background!</p>
</div>
```

**Result**: Beautiful gradient box that's not possible in visual editor!

### Safety:
- ✅ **Inline styles allowed** - `style="..."`
- ✅ **Custom classes allowed** - `class="..."`
- ✅ **H5P iframes allowed** - For interactive content
- ✅ **Most HTML tags allowed** - `<div>`, `<span>`, `<p>`, `<h1-h6>`, `<table>`, etc.
- ⚠️ **Scripts blocked** - `<script>` tags are sanitized for security

---

## 📍 Where These Features Work

Enhanced Quill editor (😀 📊 🎮 </>) is available in:
- ✅ **Edit Section** (course content) - **All features including Source Code**
- ✅ **Create Announcement** (announcement content) - **All features including Source Code**
- ✅ **Create Course** (course description) - Emojis, Tables, H5P
- ✅ **Add Assignment** (assignment description) - Emojis, Tables, H5P

**Note**: Source Code editor (</>) is only available in Edit Section and Create Announcement for teachers.

---

## 🔧 Technical Details

### Files Created:
- `/app/static/js/quill-enhanced.js` - Main enhanced Quill script
- `/app/static/css/quill-buttons.css` - Custom button styling

### Pages Updated:
- `edit_section.html`
- `create_course_wizard.html`
- `add_assignment.html`
- `create_announcement.html`
- `base_student.html` (for viewing H5P content)

### Dependencies:
- Quill 1.3.6 (rich text editor)
- Quill Better Table (table support)
- H5P Resizer Script (for interactive content)

---

## 💡 Tips & Best Practices

### For H5P:
- **Start simple**: Try Interactive Video first
- **Test as student**: Always preview content before publishing
- **Edit anytime**: Changes sync automatically
- **Use free examples**: Browse H5P.org for inspiration

### For Tables:
- **Keep it simple**: 3-5 columns max for readability
- **Use headers**: First row should be headers
- **Mobile-friendly**: Tables auto-resize on mobile

### For Emojis:
- **Use sparingly**: 1-2 per section for emphasis
- **Context matters**: Use relevant emojis
- **Accessibility**: Don't rely only on emojis for meaning

---

## 🆘 Troubleshooting

### H5P not showing?
- ✅ Check you pasted the **embed URL**, not the resizer script
- ✅ URL should look like: `https://h5p.org/h5p/embed/XXXXX`
- ✅ Or full iframe code: `<iframe src="..."></iframe>`
- ✅ Make sure content is **public** on H5P.org/com

### H5P not interactive?
- ✅ H5P resizer script is already added to student view
- ✅ Content should work automatically
- ✅ Try a different browser if issues persist

### Buttons not showing?
- ✅ Hard refresh browser: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- ✅ Clear browser cache
- ✅ Check browser console for errors (F12)

### Table not formatting?
- ✅ Right-click cells for options
- ✅ Use toolbar buttons to format text inside cells
- ✅ Tables auto-style in student view

---

## 📚 Resources

- **H5P Examples**: https://h5p.org/content-types-and-applications
- **H5P Tutorials**: https://h5p.org/documentation
- **H5P Community**: https://h5p.org/forum
- **Quill Documentation**: https://quilljs.com/docs/

---

## ✅ Summary

You now have:
1. **😀 Emoji Picker** - Quick emoji insertion
2. **📊 Tables** - Create structured data
3. **🎮 H5P Integration** - Interactive content

**All working across 4 main content creation pages!**

Create engaging, interactive content for your students! 🚀
