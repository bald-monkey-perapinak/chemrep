# Risk Mitigation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task.

**Goal:** Mitigate 24 identified risks across critical, high, medium, and low severity levels

**Architecture:** Layered defense: content safety, monitoring, fallbacks, and safeguards

**Tech Stack:** Python, Node.js, Docker, GitHub Actions

---

## Critical Risks (1-6)

### Risk 1: Chemical errors in dialogue mode

**Problem:** LLM may provide chemically incorrect answers outside structured curriculum.

**Mitigation:**
- Add confidence scoring to LLM responses
- Flag low-confidence responses for human review
- Implement fact-checking layer against knowledge base

**Files:**
- Create: `bot/src/dialog/fact_checker.py`
- Modify: `bot/src/dialog/tutor_engine.py`

**Implementation:**
```python
# bot/src/dialog/fact_checker.py
class FactChecker:
    def __init__(self, retriever):
        self.retriever = retriever
    
    def check_response(self, response: str, context: str) -> dict:
        """Check if response is supported by knowledge base."""
        # Extract key claims from response
        # Search knowledge base for supporting evidence
        # Return confidence score and supporting chunks
        return {
            "confidence": 0.0-1.0,
            "supported": bool,
            "evidence": list
        }
```

### Risk 2: Voice model leak

**Problem:** Voice model compromise enables deepfake synthesis.

**Mitigation:**
- Encrypt voice models at rest
- Implement access logging
- Add model watermarking
- Restrict model access to bot process only

**Files:**
- Create: `backend/src/utils/voice_security.py`
- Modify: `bot/src/audio/tts.py`

**Implementation:**
```python
# backend/src/utils/voice_security.py
class VoiceModelSecurity:
    def __init__(self, encryption_key: str):
        self.encryption_key = encryption_key
    
    def encrypt_model(self, model_path: str) -> str:
        """Encrypt voice model file."""
        # AES-256 encryption
        pass
    
    def decrypt_model(self, encrypted_path: str) -> bytes:
        """Decrypt voice model for use."""
        pass
    
    def log_access(self, model_id: str, user_id: str):
        """Log model access for audit."""
        pass
```

### Risk 3: Playwright bot detection

**Problem:** VCS platforms may block headless browsers.

**Mitigation:**
- Implement stealth mode (undetected-chromedriver)
- Add fallback to API-based integration
- Monitor detection rates
- Prepare manual intervention workflow

**Files:**
- Create: `bot/src/vcs/stealth.py`
- Modify: `bot/src/vcs/playwright_client.py`

**Implementation:**
```python
# bot/src/vcs/stealth.py
class StealthConfig:
    @staticmethod
    def apply_stealth(context):
        """Apply stealth patches to Playwright context."""
        # Disable webdriver flag
        # Spoof user agent
        # Add realistic mouse movements
        pass
```

### Risk 4: Recording minors without consent

**Problem:** Legal violation of 152-FZ and child protection laws.

**Mitigation:**
- Implement consent management system
- Add parental consent workflow
- Provide opt-out mechanism
- Document consent in database

**Files:**
- Create: `backend/src/models/consent.py`
- Create: `backend/src/api/routes/consent.py`
- Modify: `bot/src/orchestrator/runner.py`

**Implementation:**
```python
# backend/src/models/consent.py
class ParentalConsent(Base):
    __tablename__ = "parental_consents"
    
    id = Column(UUID, primary_key=True)
    student_id = Column(UUID, ForeignKey("students.id"))
    parent_email = Column(String)
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime)
    recording_allowed = Column(Boolean, default=False)
```

### Risk 5: Bot discrediting teacher

**Problem:** Bot's words perceived as teacher's voice.

**Mitigation:**
- Add content safety filters
- Implement profanity detection
- Add educational appropriateness check
- Include disclaimer in bot responses

**Files:**
- Create: `bot/src/dialog/safety_filter.py`
- Modify: `bot/src/dialog/tutor_engine.py`

**Implementation:**
```python
# bot/src/dialog/safety_filter.py
class SafetyFilter:
    def __init__(self):
        self.profanity_list = load_profanity_list()
    
    def check_content(self, text: str) -> dict:
        """Check content for safety issues."""
        return {
            "safe": bool,
            "issues": list,
            "filtered_text": str
        }
```

### Risk 6: Hallucination on children

**Problem:** Children more susceptible to authoritative-sounding false information.

**Mitigation:**
- Lower confidence threshold for children
- Add explicit uncertainty expressions
- Implement "I'm not sure" responses
- Add fact-checking disclaimer

**Files:**
- Modify: `bot/src/dialog/tutor_engine.py`
- Modify: `bot/src/dialog/fact_checker.py`

**Implementation:**
```python
# In tutor_engine.py
def respond(self, student_input: str, student_age: int = None) -> TutorResponse:
    response = self._generate_response(student_input)
    
    # Lower confidence threshold for children
    confidence_threshold = 0.6 if student_age and student_age < 14 else 0.8
    
    if response.confidence < confidence_threshold:
        response.text = f"Я не уверен в этом. {response.text}"
        response.needs_review = True
    
    return response
```

---

## High Risks (7-13)

### Risk 7: Response delay >4s

**Problem:** Multi-step pipeline causes latency.

**Mitigation:**
- Implement response streaming
- Add parallel processing where possible
- Cache common responses
- Monitor latency metrics

**Files:**
- Create: `bot/src/audio/streaming_tts.py`
- Modify: `bot/src/orchestrator/runner.py`

**Implementation:**
```python
# bot/src/audio/streaming_tts.py
class StreamingTTS:
    def synthesize_stream(self, text: str):
        """Stream TTS audio chunks as they're generated."""
        for chunk in self.tts.synthesize_chunks(text):
            yield chunk
```

### Risk 8: VAD false triggers

**Problem:** VAD misinterprets sounds as speech.

**Mitigation:**
- Tune VAD parameters for children's voices
- Add confirmation mechanism
- Implement noise filtering
- Add visual feedback when listening

**Files:**
- Modify: `bot/src/audio/vad.py`
- Modify: `bot/src/audio/asr.py`

**Implementation:**
```python
# In vad.py
class ChildAdaptiveVAD:
    def __init__(self):
        # Lower threshold for children's quieter voices
        self.energy_threshold = 0.3  # vs 0.5 for adults
        self.speech_duration_min = 0.3  # shorter minimum for kids
```

### Risk 9: Whiteboard sync issues

**Problem:** Visual and audio channels desynchronize.

**Mitigation:**
- Implement timestamp-based sync
- Add visual cue before board updates
- Buffer board commands
- Add sync status indicator

**Files:**
- Create: `whiteboard/src/sync.js`
- Modify: `bot/src/board/client.py`

**Implementation:**
```javascript
// whiteboard/src/sync.js
class SyncManager {
    constructor() {
        this.commandBuffer = [];
        this.syncEnabled = true;
    }
    
    queueCommand(cmd, timestamp) {
        this.commandBuffer.push({ cmd, timestamp });
    }
    
    executeWhenReady() {
        // Execute commands in order with proper timing
    }
}
```

### Risk 10: Student decontextualizing bot

**Problem:** Students redirect bot off-topic.

**Mitigation:**
- Implement strict topic guard
- Add redirect responses
- Log off-topic attempts
- Add parent/teacher alerts

**Files:**
- Create: `bot/src/dialog/topic_guard.py`
- Modify: `bot/src/dialog/tutor_engine.py`

**Implementation:**
```python
# bot/src/dialog/topic_guard.py
class TopicGuard:
    def __init__(self, topic_context: str):
        self.topic_context = topic_context
    
    def is_on_topic(self, user_input: str) -> bool:
        """Check if user input is related to the lesson topic."""
        # Use embedding similarity
        pass
    
    def get_redirect_response(self) -> str:
        return "Давай вернёмся к теме урока."
```

### Risk 11: Poor ASR on children

**Problem:** Whisper trained on adult speech.

**Mitigation:**
- Fine-tune on children's speech data
- Use larger model size
- Add child-specific preprocessing
- Implement confidence-based retry

**Files:**
- Create: `bot/src/audio/child_asr.py`
- Modify: `bot/src/audio/asr.py`

**Implementation:**
```python
# bot/src/audio/child_asr.py
class ChildASR:
    def __init__(self):
        # Use medium model instead of base for better accuracy
        self.model = load_model("medium")
    
    def preprocess(self, audio):
        """Preprocess audio for children's speech."""
        # Normalize volume (kids speak quieter)
        # Apply pitch adjustment
        pass
```

### Risk 12: Session loss without resume

**Problem:** Crash loses lesson progress.

**Mitigation:**
- Implement periodic checkpoints
- Add session recovery mechanism
- Store progress in database
- Add reconnection UI

**Files:**
- Create: `bot/src/orchestrator/checkpoint.py`
- Modify: `bot/src/orchestrator/runner.py`

**Implementation:**
```python
# bot/src/orchestrator/checkpoint.py
class LessonCheckpoint:
    def save_checkpoint(self, lesson_id: str, step: int, state: dict):
        """Save lesson progress to database."""
        pass
    
    def restore_checkpoint(self, lesson_id: str) -> dict:
        """Restore lesson from last checkpoint."""
        pass
```

### Risk 13: Whiteboard crash

**Problem:** Board service failure breaks visual component.

**Mitigation:**
- Add health checks
- Implement auto-restart
- Add fallback to text-only mode
- Monitor board status

**Files:**
- Create: `whiteboard/src/health.js`
- Modify: `bot/src/board/client.py`

**Implementation:**
```javascript
// whiteboard/src/health.js
class HealthCheck {
    constructor() {
        this.lastHeartbeat = Date.now();
    }
    
    check() {
        return {
            status: Date.now() - this.lastHeartbeat < 5000 ? 'ok' : 'degraded',
            uptime: process.uptime()
        };
    }
}
```

---

## Medium Risks (14-20)

### Risk 14: Wrong teaching pace

**Problem:** Bot doesn't adapt to student understanding.

**Mitigation:**
- Implement engagement detection
- Add pause-for-questions prompts
- Track response accuracy
- Adaptive pacing algorithm

**Files:**
- Create: `bot/src/dialog/pace_controller.py`
- Modify: `bot/src/dialog/tutor_engine.py`

### Risk 15: Error cascades from notes

**Problem:** Teacher's typos propagate to all students.

**Mitigation:**
- Add validation layer for notes
- Implement change tracking
- Add teacher review before distribution
- Version control for notes

**Files:**
- Create: `backend/src/services/note_validator.py`
- Modify: `backend/src/api/routes/knowledge.py`

### Risk 16: LLM API changes

**Problem:** Model updates change behavior.

**Mitigation:**
- Pin model versions
- Add response regression tests
- Implement A/B testing
- Monitor quality metrics

**Files:**
- Create: `bot/src/llm/version_manager.py`
- Modify: `bot/src/llm/client.py`

### Risk 17: Student doesn't connect

**Problem:** Bot waits indefinitely.

**Mitigation:**
- Add connection timeout (10 min)
- Implement reminder notifications
- Auto-cancel no-show lessons
- Notify teacher

**Files:**
- Modify: `bot/src/orchestrator/runner.py`
- Modify: `bot/src/orchestrator/scheduler.py`

### Risk 18: Voice unnatural on terms

**Problem:** TTS mispronounces chemistry terms.

**Mitigation:**
- Build pronunciation dictionary
- Add phoneme customization
- Test on common terms
- Allow teacher overrides

**Files:**
- Create: `bot/src/audio/pronunciation.py`
- Modify: `bot/src/audio/tts.py`

### Risk 19: Homework not delivered

**Problem:** Email fails silently.

**Mitigation:**
- Add delivery confirmation
- Implement multiple delivery channels
- Add retry logic
- Notify teacher of failures

**Files:**
- Modify: `bot/src/orchestrator/homework.py`
- Create: `backend/src/services/notification.py`

### Risk 20: MinIO single point of failure

**Problem:** All files in one storage.

**Mitigation:**
- Implement regular backups
- Add S3-compatible redundancy
- Monitor storage health
- Document recovery procedures

**Files:**
- Create: `scripts/backup-minio.sh`
- Modify: `docker-compose.yml`

---

## Low Risks (21-24)

### Risk 21: Student records lesson

**Problem:** Technical limitation, cannot prevent.

**Mitigation:**
- Add visible recording indicator
- Include terms of use
- Educate about copyright
- Document in consent form

### Risk 22: Whiteboard overflow

**Problem:** Canvas gets cluttered.

**Mitigation:**
- Implement page/layer system
- Add clear board command
- Auto-cleanup old elements
- Limit elements per page

**Files:**
- Modify: `whiteboard/src/canvas.js`

### Risk 23: Playwright CAPTCHA/UI changes

**Problem:** Platform updates break automation.

**Mitigation:**
- Monitor for UI changes
- Add alerting on failures
- Maintain selector documentation
- Implement manual fallback

**Files:**
- Create: `bot/src/vcs/monitor.py`

### Risk 24: JWT token leak

**Problem:** Stolen token gives full access.

**Mitigation:**
- Implement token rotation
- Add refresh tokens
- Short token expiry (15 min)
- Revoke on suspicious activity

**Files:**
- Modify: `backend/src/api/routes/auth.py`
- Create: `backend/src/services/token_manager.py`

---

## Implementation Priority

1. **Immediate (Critical):** Risks 1, 4, 5, 6 - content safety and legal compliance
2. **Short-term (High):** Risks 7, 8, 10, 12 - reliability and UX
3. **Medium-term:** Risks 14-20 - quality improvements
4. **Ongoing:** Risks 21-24 - monitoring and maintenance

---

## Summary

| Category | Risks | Mitigations | Priority |
|----------|-------|-------------|----------|
| Critical | 6 | Content safety, legal compliance | Immediate |
| High | 7 | Reliability, performance | Short-term |
| Medium | 7 | Quality, monitoring | Medium-term |
| Low | 4 | Maintenance, documentation | Ongoing |
