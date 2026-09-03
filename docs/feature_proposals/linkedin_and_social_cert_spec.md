# 🔗 1-Click "Add to LinkedIn" & Social Certificate Showcase — Feature Specification

## 1. Overview & Business Value
When a student completes an accredited or vocational course at Pace Academy, they receive a verified certificate. Allowing learners to add their credential to LinkedIn and share on WhatsApp with 1 click creates an organic viral loop, driving brand awareness and incoming student registrations with zero marketing spend.

---

## 2. UI / UX Placement

### A. Certificate Claim Screen & Certificate Detail Modal
* **Location**: Right below the Certificate PDF Download button on the completed course view.
* **Actions**:
  1. **"Add to LinkedIn Profile"** (Official LinkedIn blue button with LinkedIn icon).
  2. **"Share on WhatsApp"** (WhatsApp green button).
  3. **"Copy Public Verification Link"** (1-click clipboard copy).

---

## 3. Technical Implementation

### LinkedIn Certification URL Protocol
LinkedIn supports standard deep links that pre-fill the user's profile certification form:
```
https://www.linkedin.com/profile/add?startTask=CERTIFICATION_NAME
&name={course_title}
&organizationName=Pace%20Academy
&issueYear={year}
&issueMonth={month}
&certUrl={verification_url}
&certId={certificate_code}
```

### WhatsApp One-Click Share Protocol
```
https://api.whatsapp.com/send?text=I%20just%20earned%20my%20verified%20certificate%20in%20{course_title}%20from%20Pace%20Academy!%20Check%20it%20out:%20{verification_url}
```

---

## 4. Implementation Checklist
- [ ] Add `linkedin_url` and `whatsapp_share_url` helper properties in [`app/models.py`](file:///Users/dam1mac89/Desktop/pace/app/models.py) on `Certificate`.
- [ ] Update `app/templates/student/certificate_view.html` and the celebration modal with LinkedIn and WhatsApp share buttons.
- [ ] Ensure public verification endpoint `/verify-certificate/<cert_code>` has rich OpenGraph (OG) meta tags so previews display beautifully when shared on LinkedIn/WhatsApp.
