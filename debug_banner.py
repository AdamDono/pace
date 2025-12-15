from app import create_app, db
from app.models import User, Course
import os
from flask import url_for

app = create_app()

with app.app_context():
    # 1. Findings User
    teacher = User.query.filter_by(email='adam@thedigitalacademy.co.za').first()
    if not teacher:
        print("Teacher not found!")
        exit(1)
    
    print(f"Teacher: {teacher.username} (ID: {teacher.id})")

    # 2. Finding Draft Course
    # Assuming the most recent modified draft
    course = Course.query.filter_by(teacher_id=teacher.id, is_draft=True).order_by(Course.updated_at.desc()).first()
    
    if course:
        print(f"Found Draft Course: '{course.title}' (ID: {course.id})")
        print(f"Banner Image DB Value: {course.banner_image}")
        
        if course.banner_image:
            # 3. Check File Existence
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], course.banner_image)
            exists = os.path.exists(file_path)
            print(f"File Path: {file_path}")
            print(f"File Exists on Disk: {exists}")
            
            if exists:
                print(f"File Size: {os.path.getsize(file_path)} bytes")
            else:
                print("❌ FILE MISSING ON DISK")
            
            # 4. Check Route
            # We can't easily test the route logic without a client, but we can check if it would be allowed
            print(f"Upload Folder Config: {app.config['UPLOAD_FOLDER']}")
            
        else:
            print("Course has no banner image set.")
    else:
        print("No draft course found for this teacher.")

    # List all files in upload folder just in case
    print("\n--- Files in Upload Folder ---")
    try:
        files = os.listdir(app.config['UPLOAD_FOLDER'])
        for f in files:
            if 'banner' in f:
                print(f)
    except Exception as e:
        print(f"Error listing files: {e}")
