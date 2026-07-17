# 🎓 Pace Academy - Learning Management System

A modern, feature-rich LMS built with Flask, featuring interactive content, code execution, analytics, and more.

---

## 📚 Documentation Index

### **Getting Started**
- **[Quick Reference](QUICK_REFERENCE.md)** - Overview of all features and quick commands

### **Core Features**

#### **Content Creation**
- **[Quill & H5P Guide](QUILL_H5P_GUIDE.md)** - Rich text editor with tables, emojis, and H5P interactive content
- **[Code Editor Guide](CODE_EDITOR_IMPLEMENTATION_GUIDE.md)** - Monaco code editor integration
- **[How to Create Code Assignments](HOW_TO_CREATE_CODE_ASSIGNMENTS.md)** - Step-by-step guide
- **[Universal Code Execution](UNIVERSAL_CODE_EXECUTION_GUIDE.md)** - Multi-language code execution system
- **[Video Features](VIDEO_FEATURES_GUIDE.md)** - Video upload and streaming

#### **Grading & Assessment**
- **[Grading System](GRADING_SYSTEM_IMPLEMENTED.md)** - How grading works for assignments and code

#### **Analytics & Reporting**
- **[Analytics Guide](ANALYTICS_GUIDE.md)** - Teacher and admin analytics dashboard

#### **Notifications**
- **[Notification System](NOTIFICATION_SYSTEM_GUIDE.md)** - Real-time notifications and announcements

#### **User Management**
- **[User Suspension & Ban System](USER_SUSPENSION_BAN_SYSTEM.md)** - Admin controls for user management
- **[Suspension Quick Start](SUSPENSION_QUICK_START.md)** - Quick guide for suspending users

### **Admin Guides**
- **[Admin Setup Guide](ADMIN_SETUP_GUIDE.md)** - Complete admin panel setup and features

### **Technical**
- **[Email Setup](EMAIL_SETUP.md)** - Configure email notifications
- **[UX Improvements](UX_IMPROVEMENTS_GUIDE.md)** - UI/UX enhancements
- **[Testing Checklist](TESTING_CHECKLIST.md)** - QA testing guide

---

## 🚀 Quick Start

### Installation

1. **Clone the repository**
   ```bash
   cd /Users/dam1mac89/Desktop/pace
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python3 run.py
   ```

5. **Access the app**
   - Open browser: http://localhost:5000
   - Default admin: admin@hedgitalacademy.co.za / admin123

---

## ✨ Key Features

### **For Teachers:**
- ✅ Rich text editor with tables, emojis, H5P
- ✅ Code assignments with auto-grading
- ✅ Video upload and streaming
- ✅ Analytics dashboard
- ✅ Announcement system
- ✅ Course management
- ✅ Student progress tracking

### **For Students:**
- ✅ Interactive course content
- ✅ Code editor with execution
- ✅ Video lessons
- ✅ Assignment submission
- ✅ Progress tracking
- ✅ Notifications
- ✅ Profile management

### **For Admins:**
- ✅ User management
- ✅ Course approval
- ✅ Analytics & reports
- ✅ System settings
- ✅ Suspension & ban controls
- ✅ Email notifications

---

## 🛠️ Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLAlchemy (SQLite/PostgreSQL)
- **Frontend**: TailwindCSS, JavaScript
- **Rich Text**: Quill.js
- **Code Editor**: Monaco Editor
- **Code Execution**: Universal executor (Python, JavaScript, Java, C++, etc.)
- **Interactive Content**: H5P integration
- **Video**: HTML5 video with streaming

---

## 📖 Documentation

All documentation is in Markdown format in the root directory. Start with:
1. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Feature overview
2. **[QUILL_H5P_GUIDE.md](QUILL_H5P_GUIDE.md)** - Content creation
3. **[ADMIN_SETUP_GUIDE.md](ADMIN_SETUP_GUIDE.md)** - Admin features

---

## 🔧 Configuration

### Email Setup
See **[EMAIL_SETUP.md](EMAIL_SETUP.md)** for configuring email notifications.

### Code Execution
See **[UNIVERSAL_CODE_EXECUTION_GUIDE.md](UNIVERSAL_CODE_EXECUTION_GUIDE.md)** for supported languages and setup.

---

## 📝 License

Proprietary - Pace Academy

---

## 🆘 Support

For issues or questions, refer to the relevant guide in the documentation index above.

---

**Built with ❤️ for modern education**
