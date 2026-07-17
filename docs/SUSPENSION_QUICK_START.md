# ⚡ User Suspension/Ban System - Quick Start

## 🚀 30-Second Setup

### Step 1: Run Migration
```bash
cd /Users/dam1mac89/Desktop/pace
source .venv/bin/activate
PYTHONPATH=/Users/dam1mac89/Desktop/pace python3 migrations/add_suspension_fields.py
```

### Step 2: Restart Server
```bash
flask run
```

### Step 3: Test It
1. Login as admin
2. Go to **Users** page
3. Click yellow **⚠️** icon to suspend a user
4. Fill form and submit
5. Done! ✅

---

## 🎯 Quick Actions

### Suspend User (Temporary)
- **Button:** Yellow warning icon ⚠️
- **Form:**
  - Reason: "Testing suspension system"
  - Duration: 7 (days)
- **Result:** User locked out for 7 days

### Ban User (Permanent)
- **Button:** Red ban icon 🚫
- **Form:**
  - Reason: "Violation of terms"
- **Result:** User permanently banned

### Restore Access
- **Button:** Green checkmark ✓
- **Click:** Confirm
- **Result:** User can login again

---

## 📍 Where to Find

### Admin Panel:
- **Sidebar** → Users
- **Table** → Status column shows user state
- **Actions** → Icons on the right

### User Status Badges:
- **✓ Active** (Green) - Normal user
- **⚠️ Suspended** (Yellow) - Temporarily locked
- **🚫 Banned** (Red) - Permanently banned

---

## ✅ Success Indicators

After migration:
- [ ] See "Status" column in users table
- [ ] See action buttons (suspend/ban icons)
- [ ] Can open suspension modal
- [ ] Can suspend a test user
- [ ] User status changes to "⚠️ Suspended"
- [ ] Suspended user cannot login
- [ ] Email sent to user

---

## 🔥 What You Get

### Suspend User:
✅ Set duration (days) or indefinite  
✅ Require reason  
✅ Auto-expiration  
✅ Email notification  
✅ Login blocked  

### Ban User:
✅ Permanent action  
✅ Require reason  
✅ Email notification  
✅ Manual unban only  

### Restore User:
✅ One-click unsuspend/unban  
✅ Email notification  
✅ Immediate access  

---

## 📧 Email Examples

**Suspended:**
> "Your account is suspended until Dec 25, 2025. Reason: [...]"

**Banned:**
> "Your account has been permanently banned. Reason: [...]"

**Restored:**
> "Welcome back! Your account has been restored."

---

## 🛡️ Safety Features

- ❌ Cannot suspend yourself
- ❌ Cannot suspend other admins
- ✅ Reason is required for all actions
- ✅ Email sent for every action
- ✅ Audit trail (who suspended whom)

---

## 📚 Full Documentation

See `USER_SUSPENSION_BAN_SYSTEM.md` for:
- Complete feature list
- Technical details
- Troubleshooting guide
- Best practices

---

**Ready to use! No additional configuration needed.** 🎉
