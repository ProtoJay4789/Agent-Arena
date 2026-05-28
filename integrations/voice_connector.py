"""
Voice ↔ Game Connector — Bridges TradeRoast roasts to Speech Engine voice.

Usage:
    from integrations.voice_connector import generate_voice_roast
    
    # Generate a roast with voice
    result = await generate_voice_roast(
        roast_text="Your portfolio is down 50%. At least you're consistent.",
        severity="brutal",
        persona="steve"
    )
    # result = {"audio_path": "/tmp/xxx.mp3", "text": "...", "persona": "steve"}
"""

import asyncio
import os
import sys
from typing import Optional, Any

# Add speech engine to path
SPEECH_ENGINE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "speech-engine"
)
if os.path.exists(SPEECH_ENGINE_PATH):
    sys.path.insert(0, SPEECH_ENGINE_PATH)

# Lazy imports
_voice_tts = None
_trade_models = None
_roast_engine = None


def _load_voice_tts():
    global _voice_tts
    if _voice_tts is None:
        import voice_tts as vt  # type: ignore
        _voice_tts = vt
    return _voice_tts


def _load_roast_engine():
    global _trade_models, _roast_engine
    if _roast_engine is None:
        try:
            from core.models import TradeMetrics as TM
            from core.roast_engine import generate_roast as gr
            _trade_models = TM
            _roast_engine = gr
        except ImportError:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from core.models import TradeMetrics as TM  # type: ignore
            from core.roast_engine import generate_roast as gr  # type: ignore
            _trade_models = TM
            _roast_engine = gr
    return _trade_models, _roast_engine


async def generate_voice_roast(
    roast_text: str,
    severity: str = "medium",
    persona: str = "steve",
    output_path: Optional[str] = None,
) -> dict:
    """
    Generate a voice roast from TradeRoast output.
    
    Args:
        roast_text: The roast text from TradeRoast
        severity: mild, medium, brutal, legendary
        persona: steve or vanito
        output_path: Optional custom output path
        
    Returns:
        dict with audio_path, text, persona, severity
    """
    vt = _load_voice_tts()

    # Get voice config with severity adjustments
    voice_config = vt.get_voice_config(persona, severity)

    # Generate audio
    audio_path = await vt.text_to_speech(roast_text, voice_config)

    return {
        "audio_path": audio_path,
        "text": roast_text,
        "persona": persona,
        "severity": severity,
    }


async def generate_voice_from_metrics(metrics: dict, persona: str = "steve") -> dict:
    """
    Generate a voice roast directly from TradeMetrics.
    
    Args:
        metrics: TradeMetrics dict from TradeRoast
        persona: steve or vanito
        
    Returns:
        dict with audio_path, text, persona, severity, category
    """
    TradeMetrics, generate_roast = _load_roast_engine()

    # Convert dict to TradeMetrics if needed
    if isinstance(metrics, dict):
        trade_metrics = TradeMetrics(**metrics)
    else:
        trade_metrics = metrics

    # Generate roast
    roast_result = generate_roast(trade_metrics)

    # Generate voice
    voice_result = await generate_voice_roast(
        roast_text=roast_result.roast_text,
        severity=roast_result.severity,
        persona=persona,
    )

    return {
        **voice_result,
        "category": roast_result.category,
    }


# ── Sync wrapper for non-async contexts ──────────────────────────────────

def generate_voice_roast_sync(
    roast_text: str,
    severity: str = "medium",
    persona: str = "steve",
    output_path: Optional[str] = None,
) -> dict:
    """Synchronous wrapper for generate_voice_roast."""
    return asyncio.run(generate_voice_roast(
        roast_text=roast_text,
        severity=severity,
        persona=persona,
        output_path=output_path,
    ))


# ── Test function ────────────────────────────────────────────────────────

async def _test():
    """Quick test of the voice connector."""
    print("🎤 Testing Voice ↔ Game Connector...")

    result = await generate_voice_roast(
        roast_text=(
            "You bought at the top and sold at the bottom. "
            "That's not trading, that's donating to the market. "
            "Your portfolio is down 50 percent. "
            "At least you're consistent — consistently wrong."
        ),
        severity="brutal",
        persona="steve",
    )

    print(f"✅ Voice roast generated!")
    print(f"   Audio: {result['audio_path']}")
    print(f"   Severity: {result['severity']}")
    print(f"   Persona: {result['persona']}")

    if result['audio_path']:
        size = os.path.getsize(result['audio_path'])
        print(f"   Size: {size} bytes")

    return result


if __name__ == "__main__":
    asyncio.run(_test())
