# 🔊 "Listen to Lesson" Audio Reader (Accessibility & Commuter Mode) — Feature Specification

## 1. Overview & Business Value
Many South African vocational students study on mobile devices during daily commutes (taxis, trains, buses) or prefer auditory learning. By providing a zero-latency audio playback tool in the course reader, learners can listen to entire lesson materials hands-free without consuming heavy mobile data or requiring external audio files.

---

## 2. Technical Architecture (Zero API Cost)
Instead of expensive server-side cloud TTS APIs, this feature utilizes the **browser's native Web Speech API (`window.speechSynthesis`)**:
* **Cost**: $0.00 (Runs entirely client-side).
* **Latency**: Instant (0 ms server roundtrip).
* **Data Usage**: 0 MB extra data transferred.
* **Compatibility**: Works across Chrome, Safari, Firefox, iOS, and Android mobile browsers.

---

## 3. UI / UX Design in Course Reader

### A. Reader Top Toolbar Integration
* **Button**: `[ ▶ Listen to Lesson ]` with play/pause state.
* **Mini Audio Controller Bar**:
  * Play / Pause toggle.
  * Speed selector (`1.0x`, `1.25x`, `1.5x`).
  * Progress timeline.
  * Voice picker (en-ZA / en-GB / en-US).

### B. Dynamic Sentence Highlighting
* As the speech synthesizer reads each paragraph or sentence, the corresponding text block in `#main-reader-content` is subtly highlighted with an indigo background tint, keeping the student's eyes engaged.

---

## 4. Implementation Checklist
- [ ] Create `app/static/js/audio_reader.js` with SpeechSynthesis controller.
- [ ] Add `▶ Listen to Lesson` button in [`app/templates/student/course_detail.html`](file:///Users/dam1mac89/Desktop/pace/app/templates/student/course_detail.html) header bar.
- [ ] Implement text chunking and auto-paragraph scrolling as speech progresses.
