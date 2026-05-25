"""
Input Firewall — Never trust external data as commands.

Bankr exploit pattern:
1. Attacker sends NFT → agent processes metadata as instruction
2. Attacker posts Morse code → agent decodes and executes
3. Agent treats external text as authorized command

This module prevents all three attack vectors.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re


class InputSource(Enum):
    USER_COMMAND = "user"
    SYSTEM_EVENT = "system"
    NFT_METADATA = "nft"
    SOCIAL_MEDIA = "social"
    ON_CHAIN_MSG = "onchain"
    API_RESPONSE = "api"
    UNKNOWN = "unknown"


class ThreatLevel(Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


@dataclass
class InputVerdict:
    source: InputSource
    threat_level: ThreatLevel
    blocked: bool
    reason: str
    original_text: str


ENCODING_PATTERNS = [
    (r'^[\.\-\s]+$', "Morse code pattern"),
    (r'^(?:0x[0-9a-fA-F]+\s*)+$', "Hex-encoded content"),
    (r'^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==)?$', "Base64 content"),
    (r'^(?:\\x[0-9a-fA-F]{2})+$', "Hex escape sequence"),
    (r'\\u[0-9a-fA-F]{4}', "Unicode escape sequence"),
    (r'&#x[0-9a-fA-F]+;', "HTML hex entity"),
    (r'&#\d+;', "HTML decimal entity"),
]

COMMAND_PATTERNS = [
    r'transfer\s+\d+',
    r'send\s+\d+',
    r'move\s+funds',
    r'approve\s+transaction',
    r'sign\s+message',
    r'execute\s+swap',
    r'withdraw',
    r'drain',
]

INJECTION_MARKERS = [
    "ignore previous",
    "ignore all previous",
    "disregard instructions",
    "you are now",
    "new instructions:",
    "system prompt:",
    "override:",
    "admin mode",
    "developer mode",
    "jailbreak",
    "dan mode",
    "act as",
    "pretend you are",
    "roleplay as",
]


class InputFirewall:
    """
    Validates and sanitizes all input before it reaches the agent.

    Core rule: Only USER_COMMAND source is trusted.
    Everything else is blocked or flagged for review.
    """

    def __init__(self, trusted_sources: list[InputSource] | None = None):
        self.trusted_sources = trusted_sources or [InputSource.USER_COMMAND]
        self.blocked_count = 0
        self.flagged_count = 0

    def analyze(self, text: str, source: InputSource = InputSource.UNKNOWN) -> InputVerdict:
        """Analyze input for threats."""

        # Source trust check
        if source not in self.trusted_sources:
            self.blocked_count += 1
            return InputVerdict(
                source=source,
                threat_level=ThreatLevel.SUSPICIOUS,
                blocked=True,
                reason=f"Untrusted source: {source.value}",
                original_text=text,
            )

        # Encoding detection
        for pattern, desc in ENCODING_PATTERNS:
            if re.match(pattern, text.strip()):
                self.flagged_count += 1
                return InputVerdict(
                    source=source,
                    threat_level=ThreatLevel.MALICIOUS,
                    blocked=True,
                    reason=f"Encoded content detected: {desc}",
                    original_text=text,
                )

        # Command injection in untrusted input
        lower_text = text.lower()
        if source != InputSource.USER_COMMAND:
            for cmd_pattern in COMMAND_PATTERNS:
                if re.search(cmd_pattern, lower_text):
                    self.blocked_count += 1
                    return InputVerdict(
                        source=source,
                        threat_level=ThreatLevel.MALICIOUS,
                        blocked=True,
                        reason=f"Command pattern in untrusted input: {cmd_pattern}",
                        original_text=text,
                    )

        # Prompt injection markers
        for marker in INJECTION_MARKERS:
            if marker in lower_text:
                self.flagged_count += 1
                return InputVerdict(
                    source=source,
                    threat_level=ThreatLevel.MALICIOUS,
                    blocked=True,
                    reason=f"Prompt injection marker: {marker}",
                    original_text=text,
                )

        return InputVerdict(
            source=source,
            threat_level=ThreatLevel.SAFE,
            blocked=False,
            reason="Input passed all checks",
            original_text=text,
        )

    def get_stats(self) -> dict:
        return {
            "blocked": self.blocked_count,
            "flagged": self.flagged_count,
            "trusted_sources": [s.value for s in self.trusted_sources],
        }
