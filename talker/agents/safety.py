import re
from dataclasses import dataclass, field


CRISIS_RESOURCES = [
    "988 Suicide & Crisis Lifeline: Call or text 988 (US)",
    "Crisis Text Line: Text HOME to 741741",
    "International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/",
    "Emergency Services: Call 911 (US) or your local emergency number",
]

# Patterns that indicate immediate safety concerns
CRISIS_PATTERNS = [
    r"\b(kill|end)\s+(my\s*self|my\s*life|it\s*all)\b",
    r"\bsuicid(e|al)\b",
    r"\bwant\s+to\s+die\b",
    r"\bbetter\s+off\s+dead\b",
    r"\bno\s+reason\s+to\s+live\b",
    r"\b(cutting|hurting|harming)\s+(my\s*self|myself)\b",
    r"\bself[- ]?harm\b",
    r"\bwant\s+to\s+hurt\s+(someone|somebody|people|others)\b",
    r"\bgoing\s+to\s+hurt\b",
    r"\bplan\s+to\s+(kill|die|end)\b",
]


@dataclass
class SafetyInterrupt:
    trigger: str
    message: str
    resources: list[str] = field(default_factory=lambda: list(CRISIS_RESOURCES))


class SafetyMonitor:
    def __init__(self):
        self._patterns = [re.compile(p, re.IGNORECASE) for p in CRISIS_PATTERNS]

    def check(self, text: str) -> SafetyInterrupt | None:
        """Check text for crisis indicators. Returns SafetyInterrupt if detected."""
        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                return SafetyInterrupt(
                    trigger=match.group(),
                    message=(
                        "I'm concerned about what you've shared. Your safety is the most important thing right now. "
                        "Please reach out to one of these resources — they are available 24/7 and can help:"
                    ),
                )
        return None
