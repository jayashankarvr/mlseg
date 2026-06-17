# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Jayashankar R
"""Malayalam surface segmenter, a conservative fallback for unanalysed words.

When a full morphological analyser cannot analyse an inflected word, downstream
code still needs *some* decomposition into a stem plus its case / number
suffixes. This module provides exactly that, and nothing more: it is a small,
hand-written set of **native-ratified** surface rules, not a morphological
analyser. It does not, and must not, try to be clever.

Discipline (conservative fallback, applied to linguistics)
----------------------------------------------------------
* This is a *fallback*, never an oracle. A guess from here must never be mistaken
  for a certified analysis.
* It is **conservative by construction**: ``segment`` only ever splits on a rule
  whose surface->lemma realisation has been ratified by a native reviewer
  (reviews #2 / #3). If no rule matches, it returns ``[word]`` unsegmented. It
  NEVER invents a split, and NEVER fabricates Malayalam linguistics: every
  suffix and every surface alternation below is an attested, listed form.
* It is idempotent on bare stems: a word with no recognised suffix segments to
  itself, so re-running ``segment`` on a piece it produced is a no-op.

The ratified rules (and only these)
-----------------------------------
Suffixes (returned in their *lemma* spelling, not their surface allomorph):

  case / postposition
    locative      ``ഇൽ``                 (surface: matra ``ി`` + chillu ``ൽ``)
    sociative     ``ഓട്``
    directive     ``ലേക്ക്`` / ``ഇലേക്ക്``
    genitive      ``ഇന്റെ``              (surface: matra ``ി`` + ``ന്റെ``)
  number
    plural        ``കൾ``
    plural        ``ങ്ങൾ``               (surface before a vowel suffix: ``ങ്ങള``)

Geminate-reversion (native review #2):
  A stem whose surface ends ``…ട്ടി`` reverts to ``…ട്`` before a locative /
  directive suffix:
    വീട്ടിൽ      -> [വീട്, ഇൽ]
    നാട്ടിലേക്ക്  -> [നാട്, ലേക്ക്]
    പാലക്കാട്ടിൽ -> [പാലക്കാട്, ഇൽ]

Lemma restoration (only the sound, reversible alternations):
  * chillu: a stem whose chillu lemma surfaced as base-consonant + inherent vowel
    is restored, അവനോട് -> [അവൻ, ഓട്], കടലിൽ -> [കടൽ, ഇൽ] (``ന``->``ൻ``,
    ``ല``->``ൽ``, also ``ണ``/``ര``/``ള``). Applied consistently on every case
    branch.
  * anusvaram on ``ങ്ങൾ`` plurals only: പുസ്തകങ്ങളിൽ -> [പുസ്തകം, ങ്ങൾ, ഇൽ].

What it deliberately does NOT do (honesty over completeness):
  * It never fabricates a virama to make a lemma (the old ``നായോട് -> നായ്`` /
    ``കുട്ടിയ്`` bug). Whether a non-chillu consonant-final stem's lemma takes a
    virama (രാജാവ -> രാജാവ്) or not (നായ stays നായ) is morphology, not surface,
    so such a stem is returned in its surface form, unchanged.
  * It does not restore oblique augments (മരത്തിൽ -> [മരത്ത, ഇൽ], not [മരം, …]).
  * KNOWN LIMITATION: it has no lexicon, so an underived word of >= 2 aksharas
    that merely *ends* in a suffix-like tail can be false-split, e.g. the name
    അനിൽ -> [അന, ഇൽ]. The min-stem floor only blocks single-akshara residues;
    distinguishing the name അനിൽ from a true locative needs a lexicon/NER. Callers
    that need certainty should prefer a full analyser; this is a best-effort
    fallback for unanalysed words.

Note on normalisation: callers may pass already-normalised text; for safety the
input is run through ``mlnormalize.normalize`` so geminate / chillu comparisons are
byte-stable. The pieces returned are themselves normalised.
"""
from __future__ import annotations

from typing import List

import mlnormalize as _mlnormalize

# --- Malayalam codepoints used by the rules ----------------------------------
VIRAMA = "്"
ANUSVARA = "ം"
TTA = "ട"           # U+0D1F, the ṭa that geminates as ട്ട
I_MATRA = "ി"       # U+0D3F
CHILLU_L = "ൽ"      # U+0D7D, chillu of la (locative ഇൽ surface tail)
CHILLU_LL = "ൾ"     # U+0D7E, chillu of ḷa (plural ങ്ങൾ / കൾ tail)
LL_BASE = "ള"       # U+0D33, ḷa+inherent-a (chillu ൾ before a vowel suffix)
O_MATRA = "ോ"       # U+0D4B, surface of independent ഓ on a consonant base
N_TA_E = "ന്റെ"     # surface tail of genitive ഇന്റെ after the ഇ -> ി matra

CONSONANTS = {chr(c) for c in range(0x0D15, 0x0D3A)}  # ka..ha
INDEP_VOWELS = {chr(c) for c in range(0x0D05, 0x0D15)}  # a..au independent vowels
CHILLUS = {chr(c) for c in range(0x0D7A, 0x0D80)}        # standalone chillu letters

# Minimum residual-stem size (in aksharas) before a suffix may be stripped. A
# genuine Malayalam stem is never a single base consonant; requiring >= 2
# aksharas blocks the over-stripping of real, underived words whose tail merely
# *looks* like a suffix (e.g. മകൾ "daughter", കോട് "coat", നോട് "note").
_MIN_STEM_AKSHARAS = 2

# Surface consonant -> chillu (its word-final / pre-suffix lemma realisation).
_TO_CHILLU = {
    "ണ": "ൺ", "ന": "ൻ", "ര": "ർ", "ല": "ൽ", "ള": "ൾ",
}

# Lemma spellings of the ratified suffixes.
LOCATIVE = "ഇൽ"
SOCIATIVE = "ഓട്"
DIRECTIVE = "ലേക്ക്"
DIRECTIVE_V = "ഇലേക്ക്"   # post-vowel-stem variant
GENITIVE = "ഇന്റെ"
PLURAL_KAL = "കൾ"
PLURAL_NGAL = "ങ്ങൾ"

# Geminate surface that reverts to ``…ട്`` (ṭa + virama + ṭa + i-matra).
_TTA_GEMINATE = TTA + VIRAMA + TTA + I_MATRA       # ട്ടി
_TTA_REVERTED = TTA + VIRAMA                        # ട്


def _norm(s: str) -> str:
    return _mlnormalize.normalize(s)


def _aksharas(s: str) -> int:
    """Count orthographic syllables (aksharas) in a Malayalam string.

    A new akshara begins at any base letter (independent vowel, consonant, or
    standalone chillu) that is not immediately preceded by a virama (which would
    bind it into the preceding conjunct). Matras and the virama itself are not
    bases and never start a new akshara. This is a coarse but reliable proxy for
    "is this a plausible stem rather than a stray fragment".
    """
    count = 0
    prev_virama = False
    for ch in s:
        is_base = ch in INDEP_VOWELS or ch in CONSONANTS or ch in CHILLUS
        if is_base and not prev_virama:
            count += 1
        prev_virama = ch == VIRAMA
    return count


def _too_short(stem: str) -> bool:
    """True if ``stem`` is below the minimum-stem floor (would be over-stripping)."""
    return _aksharas(stem) < _MIN_STEM_AKSHARAS


def _restore_chillu_lemma(stem: str) -> str:
    """Restore a bare pre-suffix consonant to its chillu lemma shape, ONLY the
    sound chillu alternation, never a fabricated virama.

    The oblique stem of a chillu-final lemma surfaces with the chillu's base
    consonant carrying its inherent vowel; restoring the chillu is the standard,
    reversible alternation: ``ന`` -> ``ൻ`` (അവന- -> അവൻ), ``ല`` -> ``ൽ``
    (കടല- -> കടൽ), ``ണ``/``ര``/``ള`` likewise.

    It does NOT add a virama to other consonants. Doing so (the previous
    behaviour) fabricated WRONG lemmas on glide-/vowel-final stems,
    ``നായ`` -> ``നായ്``, ``കുട്ടിയ`` -> ``കുട്ടിയ്``, which is exactly the
    "never fabricate Malayalam" rule this module promises. Whether such a stem's
    lemma takes a virama (രാജാവ -> രാജാവ്) or not (നായ stays നായ) cannot be decided
    from the surface alone; that is morphology. So we leave the surface stem
    unchanged there rather than guess, honest, if not always the full lemma.
    Matra-/chillu-/virama-final tails are also left as is.
    """
    if not stem:
        return stem
    last = stem[-1]
    if last in _TO_CHILLU:
        return stem[:-1] + _TO_CHILLU[last]
    return stem


def _restore_anusvaram(stem: str) -> str:
    """Restore a dropped final ``ം`` on a bare stem (native review #3).

    Conservative: only restores when the stem ends in a plain consonant carrying
    its inherent vowel (no virama, no matra, no existing anusvaram), the exact
    shape a ``…ം`` lemma takes once its anusvaram is shed before an inflection
    (e.g. പുസ്തക- < പുസ്തകം). Anything else is returned untouched.
    """
    if not stem:
        return stem
    last = stem[-1]
    if last in CONSONANTS:
        return stem + ANUSVARA
    return stem


def segment(word: str) -> List[str]:
    """Split an inflected Malayalam word into [stem, *suffixes].

    Applies only native-ratified surface rules. If no rule matches, returns the
    word unsegmented (``[word]``). Suffixes are returned in their lemma spelling
    and in surface order (stem first, outermost suffix last). Idempotent on bare
    stems: ``segment`` of a word with no recognised suffix is ``[word]``.
    """
    if not word:
        return [word]

    word = _norm(word)
    rest = word
    suffixes: List[str] = []

    # --- 1. Outer case / postposition suffix ---------------------------------
    # Every strip below is guarded by ``_too_short``: a candidate residual stem
    # of fewer than _MIN_STEM_AKSHARAS aksharas means the tail only *looked* like
    # a suffix (e.g. കോട് "coat" -> ക, നോട് "note" -> ന). In that case we leave
    # ``rest`` untouched and fall through, rather than invent a bogus split.
    #
    # Directive: surface ``…ലേക്ക്``. After a consonant+ി it is the post-vowel
    # variant ``ഇലേക്ക്`` collapsing to ``…ിലേക്ക്``; after a geminate-reverting
    # stem the lemma form is ``ലേക്ക്`` (see step 2). Try the bare lemma first.
    if rest.endswith(I_MATRA + DIRECTIVE):
        # …<C>ി + ലേക്ക  -> stem keeps the ി (vowel-final), suffix ഇലേക്ക്
        # but a geminate ട്ടി stem reverts; handle that in step 2 instead.
        if rest.endswith(_TTA_GEMINATE + DIRECTIVE):
            head = rest[: -(len(_TTA_GEMINATE) + len(DIRECTIVE))]
            cand = head + _TTA_REVERTED
            if not _too_short(cand):
                rest = cand
                suffixes.insert(0, DIRECTIVE)
        else:
            cand = rest[: -len(DIRECTIVE)]   # ...ി on the stem
            base = cand[:-1]                  # drop the ി
            if base and base[-1] in _TO_CHILLU:
                # chillu noun: restore the lemma (കടല -> കടൽ) like the locative branch
                restored = _restore_chillu_lemma(base)
                if not _too_short(restored):
                    rest = restored
                    suffixes.insert(0, DIRECTIVE)
            elif not _too_short(cand):        # vowel-final stem: keep the ി
                rest = cand
                suffixes.insert(0, DIRECTIVE_V)

    elif rest.endswith(DIRECTIVE):
        cand = rest[: -len(DIRECTIVE)]
        if not _too_short(cand):
            rest = _restore_chillu_lemma(cand)
            suffixes.insert(0, DIRECTIVE)

    elif rest.endswith(I_MATRA + N_TA_E):
        # Genitive ഇന്റെ surfaces as matra ി + ന്റെ on the preceding base.
        cand = rest[: -(len(I_MATRA) + len(N_TA_E))]
        if not _too_short(cand):
            rest = _restore_chillu_lemma(cand)
            suffixes.insert(0, GENITIVE)

    elif rest.endswith(O_MATRA + SOCIATIVE[1:]):
        # Sociative ഓട് surfaces as o-matra ോ + ട് on the preceding consonant.
        cand = rest[: -(len(O_MATRA) + len(SOCIATIVE) - 1)]
        if not _too_short(cand):
            rest = _restore_chillu_lemma(cand)
            suffixes.insert(0, SOCIATIVE)

    elif rest.endswith(I_MATRA + CHILLU_L):
        # Locative ഇൽ surfaces as matra ി + chillu ൽ on the preceding base.
        # Geminate ട്ടി reverts to ട് (step 2 shape); otherwise strip ിൽ and
        # restore a chillu lemma (കടല -> കടൽ). _restore_chillu_lemma is a no-op on
        # the geminate (virama-final) stem.
        if rest.endswith(_TTA_GEMINATE + CHILLU_L):
            head = rest[: -(len(_TTA_GEMINATE) + len(CHILLU_L))]
            cand = head + _TTA_REVERTED
        else:
            cand = rest[: -(len(I_MATRA) + len(CHILLU_L))]
        if not _too_short(cand):
            rest = _restore_chillu_lemma(cand)
            suffixes.insert(0, LOCATIVE)

    # --- 2. Plural suffix (inner, between stem and any case suffix) -----------
    # ങ്ങൾ: bare it ends in chillu ൾ; before a vowel case suffix the chillu
    # surfaces as ള (ḷa + inherent a). Recognise both shapes. Each strip is again
    # floor-guarded so a real singular noun ending -കൾ (e.g. മകൾ "daughter") is
    # left whole rather than torn into a single-codepoint pseudo-stem.
    if rest.endswith(PLURAL_NGAL):
        cand = rest[: -len(PLURAL_NGAL)]
        if not _too_short(cand):
            suffixes.insert(0, PLURAL_NGAL)
            rest = _restore_anusvaram(cand)
    elif rest.endswith("ങ" + VIRAMA + "ങ" + LL_BASE):
        # surface ങ്ങള (chillu ൾ -> ള before the stripped vowel suffix)
        cand = rest[: -len("ങ" + VIRAMA + "ങ" + LL_BASE)]
        if not _too_short(cand):
            suffixes.insert(0, PLURAL_NGAL)
            rest = _restore_anusvaram(cand)
    elif rest.endswith(PLURAL_KAL):
        # കൾ plurals are NOT ം-nouns (കുട്ടികൾ<-കുട്ടി, ആളുകൾ<-ആൾ), so do NOT
        # restore anusvaram here (that was unsound); restore only a chillu lemma.
        cand = rest[: -len(PLURAL_KAL)]
        if not _too_short(cand):
            suffixes.insert(0, PLURAL_KAL)
            rest = _restore_chillu_lemma(cand)

    if not suffixes or not rest:
        # No rule matched, or stripping consumed the whole word (the input *was*
        # a bare suffix). Either way: never invent a split, return it whole.
        return [word]

    return [rest, *suffixes]
