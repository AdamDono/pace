# Pace Academy — End-to-End User Journey & Judge Demo Guide
## A Step-by-Step Walkthrough: From High School Diagnostic to Employer-Verified Credentials

**Project:** Pace Academy (Pace Tech)  
**Target Audience:** Hackathon Assessors, Enterprise Partners & Academic Evaluators  
**Version:** 1.0  

---

### User Persona: Thabo Mthembu (Age 17, Grade 11/12 Matric Candidate, Soweto)
* **Goal:** Qualify for a university degree in Computer Science / Information Systems or secure an accredited, high-demand tech job.
* **Pain Points:** Struggling with Pure Mathematics (48%); private tutoring is unaffordable (R350/hr); has no career guidance and doesn't know his university Admission Point Score (APS) until it is too late.

---

## 1. The 5-Stage Journey: High School to Workplace Placement

### Stage 1: Instant Academic Diagnostic (Report Card OCR & APS Calculation)
Thabo uploads his official term report card photo/PDF. The multimodal Vision OCR extracts his 7 CAPS subjects, detects his struggle subject (Pure Maths at 48%), and automatically computes his official university APS score (29 points) — showing he qualifies for an IT Diploma, but is 3 points shy of a University Bachelor's pass.

### Stage 2: Adaptive Study Planning & Socratic AI Tutoring
The platform automatically schedules extra study blocks for Pure Mathematics on his weekly timetable. When studying, Thabo opens **Bookworm**, the 24/7 Socratic Voice AI companion. Bookworm doesn't give him answers; it engages in audio-first Socratic questioning to build first-principles conceptual mastery.

### Stage 3: Hands-On Technical Skill Building (LMS)
Parallel to high school, Thabo enrolls in accredited digital courses (Web Development, Python). Without installing software, he writes and executes code inside the browser using the built-in Monaco Code Editor, receiving real-time auto-graded feedback on programming assignments.

### Stage 4: Cryptographic Credentialing & QR Verification
Upon completing the modules, Thabo is issued a tamper-proof Pace Academy Certificate. It features a unique cryptographic hash and dynamic QR code that employers or recruiters scan to view his verified code portfolio, course hours, and competencies.

### Stage 5: Enterprise Upskilling & Career Mobility
Equipped with verified digital credentials and an improved matric APS score, Thabo qualifies for higher education bursaries and entry-level corporate learnerships tracked directly through Pace Academy's B2B enterprise portal.

---

## 2. 4-Minute Judge Demo Script (Live Walkthrough Protocol)

### Step 1: The Landing Page (0:00 - 0:30)
* **Route:** `/`
* Highlight the core value proposition: *"From Matric to Market-Ready"*.
* Showcase the clean 2-column layout, live platform stats (Learners, Courses, 24/7 Live Support), and dynamic accreditation alignment badges (CAPS, QCTO, SETA).
* Click **"Start Learning Free"** to transition to the student login portal.

### Step 2: Student Dashboard & Report Card Scanner (0:30 - 1:30)
* **Route:** `/student/career-guidance`
* Log in as a student (or click Career Guidance).
* Demonstrate the **Report Card OCR Scanner**: Upload an official school report card (PNG/PDF).
* Show the zero-trust server processing: marks are extracted automatically and locked against tampering.
* Display the calculated **University APS Score**, degree qualification eligibility (BSc vs. Diploma), and the flagged **Struggle Subjects** alert.

### Step 3: Adaptive Timetable & Bookworm Voice AI (1:30 - 2:30)
* **Route:** `/student/calendar` & Floating Bookworm Mascot
* Show how the weekly timetable automatically balances study slots, scheduling extra revision time for flagged struggle subjects.
* Click the animated **Bookworm Mascot** (with floating bob, blinking eyes, and tassel sway).
* Speak or type a question: *"Bookworm, guide me through solving quadratic equations."*
* Point out the Socratic response (guiding questions, not rote answers) and the daily **Sparks Quota counter** (`50/50`).

### Step 4: Monaco Code Editor & Hands-On LMS (2:30 - 3:30)
* **Route:** `/student/course/27` (Web Development / Coding)
* Open a code lesson module.
* Show the embedded **Monaco Code Editor** (VS Code engine in browser).
* Run Python / HTML / JS code in real time with instant output in the integrated terminal.
* Demonstrate automated code assignment submission and immediate auto-grading feedback.

### Step 5: Verifiable Digital QR Certificates & Teacher Hub (3:30 - 4:00)
* **Route:** `/student/certificates` & `/teacher/dashboard`
* View the issued Certificate of Completion.
* Scan the **Dynamic QR Code** on a mobile phone to show the public tamper-proof verification page.
* Briefly switch to the Teacher/Admin dashboard to show class progress analytics, course authoring, and B-BBEE corporate tracking.

---

## 3. Pre-Configured Test Credentials & Navigation Matrix

| Portal Role | Demo Email | Key Features to Evaluate | Target Route |
| :--- | :--- | :--- | :--- |
| **Student** | `learner@gmail.com` | Report Card OCR, University APS, Bookworm Voice AI, Monaco IDE, QR Certificate | `/student/dashboard` |
| **Teacher** | `adam@thedigitalacademy.co.za` | Modular Course Builder, Monaco Code Assignment Setup, Class Analytics, Grading | `/teacher/dashboard` |
| **Admin** | `admin@pace.com` | User Management, Course Approval Workflow, System Logs, B2B Leads & B-BBEE Reports | `/admin/dashboard` |

---

**Summary for Assessors:** This user journey reflects a cohesive, production-deployed platform that addresses every stage of South Africa's educational and youth employment funnel. All listed features are active and testable in the live environment.
