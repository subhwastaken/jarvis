"""Backward Compatibility Layer for System One Decision Engine.
Delegates entirely to `laya_engine.py` (Laya Decision Engine).
"""
from laya_engine import (
    LayaDecisionEngine,
    get_laya_engine,
    laya_decide,
    APPS,
    LEVEL_WORDS,
    QUESTIONS
)

# Aliases for backward compatibility
SystemOneRouter = LayaDecisionEngine
get_router = get_laya_engine
