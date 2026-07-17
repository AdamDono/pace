# 📧 Email Notification System Setup Guide

## Overview
The PACE LMS now includes an automated email notification system that sends emails for:
- ✅ **Welcome emails** when admin creates a new user account (includes login credentials)
- ✅ **Enrollment notifications** when students are enrolled in courses
- ✅ **Course approval emails** to teachers (optional, ready to implement)
- ✅ **Course rejection emails** to teachers (optional, ready to implement)

---

## 🚀 Quick Setup

### Step 1: Install Flask-Mail
```bash
pip install -r requirements.txt
```

### Step 2: Configure Email Settings

Copy `.env.example` to `.env` and update with your email credentials:

```bash
cp .env.example .env
```

### Step 3: Choose Your Email Provider

#### **Option A: Gmail (Recommended for Testing)**

1. **Enable 2-Factor Authentication** on your Google account
2. **Generate an App Password:**
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and your device
   - Copy the 16-character password

3. **Update .env file:**
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-char-app-password
MAIL_DEFAULT_SENDER=noreply@paceacademy.com
BASE_URL=http://localhost:5000
```

#### **Option B: SendGrid (Recommended for Production)**

1. Sign up at https://sendgrid.com (Free tier: 100 emails/day)
2. Create an API Key
3. **Update .env file:**
```env
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=apikey
MAIL_PASSWORD=your-sendgrid-api-key
MAIL_DEFAULT_SENDER=noreply@yourdomain.com
BASE_URL=https://yourdomain.com
```

#### **Option C: Mailgun**

```env
MAIL_SERVER=smtp.mailgun.org
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=postmaster@your-domain.mailgun.org
MAIL_PASSWORD=your-mailgun-password
MAIL_DEFAULT_SENDER=noreply@yourdomain.com
```

#### **Option D: Outlook/Office 365**

```env
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@outlook.com
MAIL_PASSWORD=your-password
MAIL_DEFAULT_SENDER=your-email@outlook.com
```

---

## 📨 Email Types & Triggers

### 1. **Welcome Email**
- **Triggered when:** Admin creates a new user (student or teacher)
- **Recipients:** New user
- **Contents:**
  - Welcome message
  - Login credentials (email & password)
  - Link to login page
  - Security reminder to change password
- **Template:** `app/templates/emails/welcome.html`

### 2. **Enrollment Email**
- **Triggered when:** Teacher enrolls a student in a course
- **Recipients:** Enrolled student
- **Contents:**
  - Course title and description
  - Link to course page
  - Learning tips
- **Template:** `app/templates/emails/enrollment.html`

### 3. **Course Approved Email** *(Optional)*
- **Triggered when:** Admin approves a teacher's course
- **Recipients:** Course teacher
- **Contents:**
  - Congratulations message
  - Link to course management
  - Next steps guidance
- **Template:** `app/templates/emails/course_approved.html`

### 4. **Course Rejected Email** *(Optional)*
- **Triggered when:** Admin rejects a teacher's course
- **Recipients:** Course teacher
- **Contents:**
  - Admin feedback
  - Link to edit course
  - Tips for improvement
- **Template:** `app/templates/emails/course_rejected.html`

---

## 🧪 Testing

### Test Email Configuration

Create a test script `test_email.py`:

```python
from app import create_app
from app.utils.email import send_email

app = create_app()

with app.app_context():
    result = send_email(
        subject='Test Email from Pace Academy',
        recipient='your-test-email@gmail.com',
        template='welcome',
        user={'username': 'TestUser', 'email': 'test@example.com'},
        password='test123',
        login_url='http://localhost:5000/login'
    )
    print(f"Email sent: {result}")
```

Run the test:
```bash
python test_email.py
```

---

## 🔍 Troubleshooting

### Problem: "SMTPAuthenticationError"
**Solution:** 
- Gmail: Make sure you're using an App Password, not your regular password
- Verify 2FA is enabled
- Check MAIL_USERNAME is the full email address

### Problem: "SMTPConnectError"
**Solution:**
- Check MAIL_SERVER and MAIL_PORT are correct
- Ensure MAIL_USE_TLS is set to `true`
- Check firewall/antivirus isn't blocking port 587

### Problem: Emails not sending
**Solution:**
- Check logs: `tail -f app.log`
- Verify email credentials in .env
- Test with a simpler email provider (Gmail) first
- Check spam folder

### Problem: "Connection refused"
**Solution:**
- For Gmail: Enable "Less secure app access" (not needed if using App Password)
- Check if your IP is blocked by the email provider
- Try a different port (465 for SSL instead of 587 for TLS)

---

## 🎨 Customizing Email Templates

All email templates are in `app/templates/emails/`:

### Adding Your Logo
Replace the text logo with an image:
```html
<img src="{{ url_for('static', filename='images/logo.png', _external=True) }}" 
     alt="Pace Academy" 
     style="max-width: 200px;">
```

### Changing Colors
Update the inline CSS:
```html
<style>
    .button {
        background-color: #YOUR_COLOR;
    }
    .logo .pace {
        color: #YOUR_COLOR;
    }
</style>
```

### Adding Custom Content
Edit the HTML files directly. Variables available:
- `user` - User object (username, email, role)
- `course` - Course object (title, description)
- `student` - Student user object
- `teacher` - Teacher user object
- `password` - Plain text password (welcome email only)
- `feedback` - Admin feedback text

---

## 🔒 Security Best Practices

1. **Never commit .env file** - It's in .gitignore
2. **Use App Passwords** - Don't use your actual email password
3. **Async sending** - Emails are sent in background threads (already implemented)
4. **Error handling** - Email failures won't crash the app
5. **Production:** Use a dedicated email service (SendGrid, Mailgun, AWS SES)

---

## 📊 Production Recommendations

### For Production Deployment:

1. **Use a professional email service:**
   - SendGrid (100 emails/day free)
   - Mailgun (5,000 emails/month free)
   - AWS SES (62,000 emails/month free)

2. **Set up email tracking:**
   - Add open tracking
   - Add click tracking
   - Monitor bounce rates

3. **Add email queue:**
   - Use Celery for background tasks
   - Redis for task queue
   - Better reliability for high volume

4. **Domain authentication:**
   - Set up SPF records
   - Set up DKIM
   - Set up DMARC
   - Improves deliverability

---

## 🔄 Future Enhancements

Want to add more email notifications? Easy! Just:

1. Create a new template in `app/templates/emails/`
2. Add a function in `app/utils/email.py`
3. Call the function where needed in your routes

Example for assignment submission notification:
```python
# In app/utils/email.py
def send_assignment_submitted_email(teacher, student, assignment):
    return send_email(
        subject=f'{student.username} submitted {assignment.title}',
        recipient=teacher.email,
        template='assignment_submitted',
        teacher=teacher,
        student=student,
        assignment=assignment
    )
```

---

## ✅ Verification Checklist

- [ ] Flask-Mail installed (`pip list | grep Flask-Mail`)
- [ ] `.env` file configured with email credentials
- [ ] Email templates exist in `app/templates/emails/`
- [ ] Test email sent successfully
- [ ] Welcome email works when creating users
- [ ] Enrollment email works when enrolling students
- [ ] Emails appear professional and branded
- [ ] Links in emails work correctly
- [ ] Emails don't go to spam folder

---

## 📞 Support

If you need help:
1. Check the logs for error messages
2. Test with Gmail first (simplest setup)
3. Verify your credentials are correct
4. Check firewall/antivirus settings
5. Review Flask-Mail documentation: https://pythonhosted.org/Flask-Mail/

---

## 🎉 You're All Set!

Your PACE LMS now has a fully functional email notification system. Students will receive welcome emails with their login credentials, and enrollment notifications when added to courses!
