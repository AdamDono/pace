# 🎯 How to Create Code Assignments - Quick Guide

## ✅ Step-by-Step Instructions

### **Option 1: From Course Management (Recommended)**

1. **Go to Teacher Dashboard**
   - Click "My Courses"

2. **Open Your Course**
   - Click "Manage" button on any course

3. **Expand a Module**
   - Click on any module to expand it
   - Click on a section to see details

4. **Add Assignment**
   - Click the green "**+ Add Assignment**" button
   - This appears under each section

5. **Fill in Assignment Details**
   - **Title:** e.g., "Python Basics - Variables"
   - **Description:** Use the rich text editor (Quill) to format instructions
   - **Due Date:** Optional

6. **Enable Code Assignment Features** (See the purple box below)
   - Check ☑️ "**This is a coding assignment**"
   - Select **Programming Language** (Python, JavaScript, Java, C++, HTML, SQL)
   - Add **Starter Code** (optional - template for students)
   - Check ☑️ "**Allow students to run code in browser**" (enables execution)
   - Check ☑️ "**Allow file uploads**" (students can upload .py, .js files)

7. **Save**
   - Click "📝 Create Assignment"

---

### **Option 2: Direct URL**

If you know your course and section IDs:
```
/teacher/course/<course_id>/section/<section_id>/add-assignment
```

Example:
```
/teacher/course/1/section/5/add-assignment
```

---

## 💻 What Code Assignment Features Look Like

When you check "This is a coding assignment", you'll see:

```
┌─────────────────────────────────────────────────┐
│ 💻 Code Assignment Settings                    │
├─────────────────────────────────────────────────┤
│                                                 │
│ ☑️ This is a coding assignment                 │
│                                                 │
│ Programming Language: [Python ▼]               │
│                                                 │
│ Starter Code (Optional):                       │
│ ┌─────────────────────────────────────────┐   │
│ │ # Write your code here                  │   │ ← CodeMirror
│ │ def solve():                            │   │   editor
│ │     pass                                │   │
│ └─────────────────────────────────────────┘   │
│                                                 │
│ ☑️ Allow students to run code in browser       │
│ ☑️ Allow file uploads (.py, .js, etc.)         │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 🎓 Student Experience

When students open a code assignment, they see:

```
┌─────────────────────────────────────────────────┐
│ Assignment: Python Basics                      │
├─────────────────────────────────────────────────┤
│ 📋 Instructions                                 │
│ [Rich text with your instructions]             │
├─────────────────────────────────────────────────┤
│ Your Code (PYTHON)    [🔄][📋][▶️ Run]        │
│ ┌─────────────────────────────────────────┐   │
│ │  1  def solve():                        │   │
│ │  2      # Student writes code here      │   │
│ │  3      return result                   │   │
│ └─────────────────────────────────────────┘   │
│                                                 │
│ Console Output:                                 │
│ ┌─────────────────────────────────────────┐   │
│ │ ✅ Success!                             │   │
│ │ Hello World                             │   │
│ └─────────────────────────────────────────┘   │
│                                                 │
│ [✅ Submit Assignment]                         │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Supported Languages

| Language | Icon | Execution Support | Syntax Highlighting |
|----------|------|-------------------|---------------------|
| Python | 🐍 | ✅ In Browser (Pyodide) | ✅ |
| JavaScript | 📜 | ✅ Native Browser | ✅ |
| Java | ☕ | ❌ (Coming Soon) | ✅ |
| C++ | ⚙️ | ❌ (Coming Soon) | ✅ |
| HTML/CSS | 🌐 | ✅ Preview Mode | ✅ |
| SQL | 🗄️ | ❌ (Coming Soon) | ✅ |

---

## 📊 Features Included

### **For Teachers:**
- ✅ Rich text instructions (Quill editor)
- ✅ Starter/template code
- ✅ Choose any of 6 languages
- ✅ Enable/disable code execution
- ✅ Enable/disable file uploads
- ✅ View student code with syntax highlighting
- ✅ See execution output
- ✅ Grade submissions

### **For Students:**
- ✅ Professional code editor (CodeMirror)
- ✅ Syntax highlighting
- ✅ Line numbers
- ✅ Auto-indentation
- ✅ Run code button (Python & JavaScript)
- ✅ Console output display
- ✅ File upload option
- ✅ Copy/reset buttons
- ✅ Character & line count

---

## 🔧 Troubleshooting

### **"Can't find Add Assignment button"**
- Make sure you've created at least one section in your module
- Expand the section to see the "Add Assignment" button

### **"Code options don't appear"**
- Make sure you checked ☑️ "This is a coding assignment"
- The code options panel will appear below when checked

### **"Students can't run code"**
- Make sure "Allow students to run code" is checked
- Python execution loads on first use (2-3 seconds)
- JavaScript runs instantly

### **"Starter code doesn't save"**
- Make sure to type in the CodeMirror editor
- The code auto-saves when you submit the form

---

## 📖 Example Assignment

**Title:** Introduction to Python Functions

**Instructions (in Quill editor):**
```
Write a function called calculate_sum that:
- Takes a list of numbers as input
- Returns the sum of all numbers
- Handles empty lists by returning 0

Example:
- Input: [1, 2, 3, 4]
- Output: 10
```

**Starter Code:**
```python
def calculate_sum(numbers):
    """
    Calculate the sum of all numbers in the list.
    
    Args:
        numbers: List of integers
        
    Returns:
        int: Sum of all numbers
    """
    # TODO: Write your code here
    pass

# Test your function
print(calculate_sum([1, 2, 3, 4]))  # Should print 10
print(calculate_sum([]))  # Should print 0
```

**Settings:**
- Language: Python
- Run Code: ✅ Enabled
- File Upload: ✅ Enabled

---

## 🎊 You're Ready!

Just follow these steps:
1. Go to course → Manage
2. Expand module → Expand section
3. Click "+ Add Assignment"
4. Check "This is a coding assignment"
5. Fill in details and save!

**Students will love the professional code editor!** 🚀

---

## 📝 Notes

- Code assignments are stored separately from regular assignments
- Students can submit either by typing code OR uploading a file
- Execution output is saved with the submission
- Teachers can see exactly what students ran and the results

**Need help?** Check `CODE_EDITOR_IMPLEMENTATION_GUIDE.md` for full details!
