import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

print("🔍 Testing Gmail SMTP Connection...")
print("=" * 50)

# Your credentials
email = "flipbrickzmusic1@gmail.com"
password = "jdadoffpqhurgdqo"
smtp_server = "smtp.gmail.com"
smtp_port = 587

try:
    print(f"📧 Email: {email}")
    print(f"🔑 Password: {password}")
    print(f"🌐 Server: {smtp_server}:{smtp_port}")
    print("\n⏳ Connecting to Gmail SMTP server...")
    
    # Create SMTP connection
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.set_debuglevel(0)  # Set to 1 for verbose output
    
    print("✅ Connected to server")
    print("🔐 Starting TLS encryption...")
    
    server.starttls()
    print("✅ TLS encryption started")
    
    print("🔑 Attempting login...")
    server.login(email, password)
    
    print("\n" + "=" * 50)
    print("✅ ✅ ✅ LOGIN SUCCESSFUL! ✅ ✅ ✅")
    print("=" * 50)
    print("\n🎉 Your Gmail credentials are working!")
    print("📧 Emails will send successfully from Pace Academy")
    
    server.quit()
    print("\n✅ Connection closed")
    
except smtplib.SMTPAuthenticationError as e:
    print("\n" + "=" * 50)
    print("❌ AUTHENTICATION FAILED")
    print("=" * 50)
    print(f"\nError: {e}")
    print("\n🔧 Possible fixes:")
    print("1. Make sure 2FA is enabled on your Gmail")
    print("2. Generate a NEW App Password at:")
    print("   https://myaccount.google.com/apppasswords")
    print("3. Make sure you're using the App Password, not your Gmail password")
    
except smtplib.SMTPException as e:
    print("\n❌ SMTP Error:", e)
    
except Exception as e:
    print("\n❌ Unexpected Error:", e)
    print(f"Error type: {type(e).__name__}")
