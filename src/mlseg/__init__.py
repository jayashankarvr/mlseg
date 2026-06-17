# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Jayashankar R
"""A rule-based Malayalam surface segmenter (conservative morphological fallback)."""
from .segment import segment, LOCATIVE, SOCIATIVE, DIRECTIVE, DIRECTIVE_V, GENITIVE, PLURAL_KAL, PLURAL_NGAL

__version__ = "0.1.0"
__all__ = [
    "segment",
    "LOCATIVE",
    "SOCIATIVE",
    "DIRECTIVE",
    "DIRECTIVE_V",
    "GENITIVE",
    "PLURAL_KAL",
    "PLURAL_NGAL",
    "__version__",
]
