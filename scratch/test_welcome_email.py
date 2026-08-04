import time
from app import create_app
from app.utils.email import send_welcome_email

app = create_app()
with app.app_context():
    # Force sender and keys to match the new configuration
    app.config['MAIL_DEFAULT_SENDER'] = 'Pace Academy <flipbrickzmusic1@gmail.com>'
    
    class MockUser:
        email = 'adamdono100@gmail.com'
        first_name = 'Adam'
        username = 'adamdono'
    
    user = MockUser()
    print("Queueing welcome email via Brevo HTTP API...")
    success = send_welcome_email(user, 'TestPassword123!')
    print(f"Queued successfully: {success}")
    
    # Wait for the async thread to execute
    print("Waiting for thread to send...")
    time.sleep(5)
    print("Test finished. Please check your email inbox at adamdono100@gmail.com!")
