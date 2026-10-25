# Secure System Development Life Cycle (SSDLC)
## Pace Tech — System Security Documentation

**Project:** Pace Tech  
**Document Version:** 1.0  
**Compliance Standards:** POPIA (Act 4 of 2013), OWASP Top 10, NIST Cybersecurity Framework  

---

## 1. Security Requirements (Risk Assessment)

### Asset Classification
- **Sensitive Personal Data (POPIA / Minors):** Student academic history, official CAPS school report cards, calculated APS scores, biographical data, and audio recordings submitted to the AI tutor.
- **System Secrets:** Database credentials (`DATABASE_URL`), session encryption keys (`SECRET_KEY`), external AI API keys (Google Gemini), and SMTP mail credentials.
- **Operational Data:** Course curriculum, assignments, gradebooks, attendance logs, and student timetable schedules.

### Identified Risks & Mitigations
- **Academic Mark Tampering (Critical):** Students modifying marks to artificially inflate their APS scores.  
  *Mitigation:* Strict zero-trust input model. Manual entry of marks is blocked. Marks are extracted directly from official report cards via server-side OCR/vision and permanently locked (`is_verified = True`).
- **Unauthorized Data Access & IDOR (High):** Students or external users attempting to access another learner's academic records or report files.  
  *Mitigation:* Server-side authorization checks on every endpoint. Queries are strictly scoped to the authenticated session (`current_user.id`).
- **Session Hijacking & Credential Stuffing (High):** Unauthorized account takeover.  
  *Mitigation:* Salted PBKDF2/SHA-256 password hashing, `HttpOnly` and `SameSite=Lax` cookies, 9-hour inactivity session expiration, and role validation.
- **Resource Exhaustion / Denial of Service (Medium):** Flooding file upload endpoints with massive files or audio streams.  
  *Mitigation:* Server-enforced payload caps (`MAX_CONTENT_LENGTH = 100MB`), memory limits (`MAX_FORM_MEMORY_SIZE = 50MB`), and file extension whitelisting.

---

## 2. Threat Modelling & Design Review

### STRIDE Threat Model
Pace Tech applies the STRIDE model across all application layers (Browser Client -> Reverse Proxy -> Flask Web Server -> PostgreSQL Database -> External AI Services):

- **Spoofing:** Defended via cryptographically signed Flask session cookies, salted PBKDF2 password hashing, and role-based access decorators (`@login_required`, `@roles_required`).
- **Tampering:** Defended via an upload-only report card pipeline. Clients cannot submit arbitrary mark arrays or edit their APS score. The backend processes the uploaded file directly, extracts subject marks, computes the APS using the standard South African university formula, and stores an immutable record.
- **Repudiation:** Enforced by attaching immutable UTC timestamps (`confirmed_at`, `created_at`) and foreign keys to student actions (timetable confirmations, assignment submissions).
- **Information Disclosure:** Defended against Insecure Direct Object References (IDOR). All database lookups for student records enforce `filter_by(student_id=current_user.id)` rather than trusting client-supplied URL IDs.
- **Denial of Service:** Handled by bounding request bodies to 100MB, form field buffers to 50MB, client audio recordings to 30 seconds, and enforcing database connection pooling.
- **Elevation of Privilege:** User roles (`student`, `teacher`, `admin`) are strictly server-managed and cannot be altered through client-side profile forms.

---

## 3. Development (Secure Coding Practices)

Pace Tech implements the following defensive engineering practices:

- **Anti-Tamper Report Card Pipeline:** Uploaded filenames are sanitized using Werkzeug's `secure_filename()` to block Directory Traversal (`../../`). Files are restricted to verified extensions (`.pdf`, `.png`, `.jpg`, `.jpeg`) and stored in isolated directories outside the web root.
- **CSRF Protection:** Global `CSRFProtect` is enabled across all blueprints. State-changing POST/PUT requests require a valid cryptographic `X-CSRFToken`.
- **SQL Injection Prevention:** 100% of database access is handled via SQLAlchemy ORM with parameterized queries. No raw SQL string interpolation is permitted.
- **XSS Prevention:** Global Jinja2 HTML auto-escaping is active across all templates. User inputs are never rendered unescaped.
- **Session & Cookie Hardening:** Session cookies use `HttpOnly = True` to mitigate cookie theft via script injection, `SameSite = 'Lax'`, and a 9-hour session inactivity lifetime.
- **Secrets Management:** Zero credentials are stored in code. All secrets are loaded from environment variables (`.env`) via `python-dotenv`.
- **Proxy Security:** Werkzeug `ProxyFix` middleware is enabled to correctly resolve client IP addresses and protocol headers behind reverse proxies (Render / Cloudflare).

---

## 4. Security Testing

Security testing is divided into automated analysis, dependency vulnerability scanning, and manual penetration testing simulations:

- **Static Application Security Testing (SAST):** Automated scans using Bandit and Flake8 verify zero critical flaws, no insecure functions (`eval`, `exec`), no hardcoded secrets, and proper exception handling.
- **Software Composition Analysis (SCA):** Scanned third-party Python packages using `pip-audit` against known vulnerabilities in the National Vulnerability Database (NVD).
- **Dynamic Security Testing (DAST) & Logic Verification:**
  - *Mark Tampering Test:* Sent an HTTP POST to `/student/api/career/upload-report` containing injected mark values in JSON. The backend rejected the payload, accepting only multipart binary file streams.
  - *IDOR Probe:* Attempted accessing another student's report and timetable by changing URL path parameters. The request was rejected with HTTP 403/404 because the queries enforce session ownership.
  - *CSRF Fuzzing:* Dispatched state-changing POST requests without CSRF tokens. All were blocked with HTTP 400 Bad Request.
  - *Payload Limit Test:* Attempted uploading payloads exceeding 100MB. The web server dropped the connection with HTTP 413 Payload Too Large.

---

## 5. Assessment & Secure Integration

- **External AI Integration (Google Gemini API):**
  - All communications occur over outbound TLS 1.3 with verified CA certificates (`certifi`).
  - Report cards and audio streams are processed ephemerally for inference only; no data is retained in third-party model training datasets.
  - Model outputs are validated against strict JSON schemas before database storage, discarding any hallucinated or malformed structures.
- **Infrastructure & Reverse Proxy Hardening:**
  - Enforced HTTPS with HSTS headers in production.
  - Werkzeug `ProxyFix` middleware ensures accurate remote IP attribution for security logging and rate-limiting.
- **POPIA & Data Privacy Compliance:**
  - Strict role isolation ensures student academic records remain private to the student and authorized teachers.
  - Architecture is designed for clean third-party integration (e.g. bursary verification or payment gateways like Paystack) using authenticated APIs and HMAC-signed webhooks.
