# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Jayashankar R
"""Tests for the Malayalam surface segmenter (mlseg.segment).

Real behaviour tests, every case exercises ``segment`` end to end on actual
Malayalam strings (no mocks). They lock in the native-ratified rules and, just
as importantly, the conservative contract: unknown input is returned unsplit and
the segmenter is idempotent on the pieces it produces.
"""
from __future__ import annotations

import mlnormalize
import pytest

from mlseg import segment


# --- The cases that MUST pass (native review #2 / #3) -------------------------

def test_plural_kal():
    assert segment("കുട്ടികൾ") == ["കുട്ടി", "കൾ"]


def test_geminate_reversion_locative():
    # വീട്ടി reverts to വീട് before the locative ഇൽ
    assert segment("വീട്ടിൽ") == ["വീട്", "ഇൽ"]


def test_geminate_reversion_directive():
    # നാട്ടി reverts to നാട് before the directive ലേക്ക്
    assert segment("നാട്ടിലേക്ക്") == ["നാട്", "ലേക്ക്"]


def test_directive_restores_chillu_lemma():
    # A chillu-final noun restores its lemma before the directive, like the locative
    # (കടലിലേക്ക് -> കടൽ, parallel to കടലിൽ -> കടൽ). A vowel-final stem keeps its ി.
    assert segment("കടലിലേക്ക്") == ["കടൽ", "ലേക്ക്"]
    assert segment("സ്കൂളിലേക്ക്") == ["സ്കൂൾ", "ലേക്ക്"]


def test_geminate_reversion_compound_stem():
    # multi-syllable stem പാലക്കാട്ടി -> പാലക്കാട് + ഇൽ
    assert segment("പാലക്കാട്ടിൽ") == ["പാലക്കാട്", "ഇൽ"]


def test_lemma_restoration_anusvaram_chain():
    # plural + locative, base lemma keeps its ം
    assert segment("പുസ്തകങ്ങളിൽ") == ["പുസ്തകം", "ങ്ങൾ", "ഇൽ"]


# --- Negative: no known suffix -> unsegmented --------------------------------

def test_no_suffix_returns_whole_word():
    assert segment("മരം") == ["മരം"]


@pytest.mark.parametrize("word", ["വീട്", "നാട്", "കുട്ടി", "പുസ്തകം", "പാലക്കാട്"])
def test_bare_stem_is_unsegmented(word):
    assert segment(word) == [word]


# --- Idempotence: re-segmenting a produced piece is a no-op -------------------

@pytest.mark.parametrize(
    "word",
    [
        "കുട്ടികൾ",
        "വീട്ടിൽ",
        "നാട്ടിലേക്ക്",
        "പുസ്തകങ്ങളിൽ",
        "പാലക്കാട്ടിൽ",
        "മരം",
    ],
)
def test_idempotent_on_stem(word):
    """The stem (first piece) must itself segment to itself."""
    pieces = segment(word)
    stem = pieces[0]
    assert segment(stem) == [stem]


def test_bare_suffix_is_not_split_to_empty_stem():
    # A bare suffix string must never produce an empty stem; return it whole.
    for suffix in ["ഇൽ", "ങ്ങൾ", "കൾ", "ലേക്ക്", "ഓട്", "ഇന്റെ"]:
        assert segment(suffix) == [suffix]


# --- Other ratified suffixes -------------------------------------------------

def test_plural_ngal_with_anusvaram():
    # bare plural (no case suffix): ം lemma restored, chillu form ങ്ങൾ
    assert segment("മരങ്ങൾ") == ["മരം", "ങ്ങൾ"]


def test_sociative_surface():
    # sociative ഓട് surfaces as o-matra on the consonant; the bare stem is
    # restored to its lemma (final ന -> chillu ൻ): അവൻ, not the fragment അവന.
    assert segment("അവനോട്") == ["അവൻ", "ഓട്"]


def test_genitive_surface():
    # genitive ഇന്റെ surfaces as ി + ന്റെ. The stem is returned in SURFACE form
    # (രാജാവ): whether its lemma takes a virama (രാജാവ്) is morphology, not surface,
    # so the segmenter does not fabricate one (it only restores sound chillu lemmas).
    assert segment("രാജാവിന്റെ") == ["രാജാവ", "ഇന്റെ"]


def test_no_virama_fabrication_on_glide_or_vowel_stems():
    # regression: the old _restore_consonant_lemma wrongly appended a virama to
    # any consonant, producing നായ് / കുട്ടിയ്. A glide/vowel-final stem must be
    # left in its surface form, never fabricated.
    assert segment("നായോട്") == ["നായ", "ഓട്"]
    assert segment("കുട്ടിയോട്") == ["കുട്ടിയ", "ഓട്"]


def test_chillu_restoration_consistent_on_locative():
    # chillu lemma restoration applies on EVERY case branch, not just sociative/
    # genitive: കടല -> കടൽ before the locative.
    assert segment("കടലിൽ") == ["കടൽ", "ഇൽ"]


def test_kal_plural_no_anusvaram():
    # കൾ plurals are not ം-nouns; the stem must not gain a fabricated anusvaram.
    assert segment("ആളുകൾ") == ["ആളു", "കൾ"]


def test_geminate_reversion_locative_via_directive_variant():
    # geminate stem + directive (lemma form ലേക്ക്, not the post-vowel ഇലേക്ക്)
    assert segment("വീട്ടിലേക്ക്") == ["വീട്", "ലേക്ക്"]


# --- Conservatism: real (non-inflected) words must NOT be over-stripped ------

@pytest.mark.parametrize(
    "word",
    [
        "മകൾ",   # "daughter": singular noun ending -കൾ, NOT a plural
        "കോട്",  # "coat / fort": ends in the sociative ഓട് surface, not sociative
        "നോട്",  # "note": likewise ends in ഓട് surface, not sociative
    ],
)
def test_real_word_not_over_stripped(word):
    # The residual would be a single base consonant (ക/ന/മ), an impossible
    # Malayalam stem. The minimum-stem floor must reject the split and return
    # the word whole, never fabricating a stem (and never an anusvaram one).
    assert segment(word) == [word]


# --- Conservatism: only ratified surface allomorphs split --------------------

def test_plural_locative_recovered_via_chillu_restoration():
    # കുട്ടികളിൽ = കുട്ടി + കൾ(plural, surface കള before the vowel) + ഇൽ. Restoring
    # the locative stem's chillu (കള -> കൾ) re-exposes the plural, giving the full
    # three-piece segmentation, the correct decomposition of "in the children".
    assert segment("കുട്ടികളിൽ") == ["കുട്ടി", "കൾ", "ഇൽ"]


def test_floor_blocks_false_plural_strip():
    # മുകളിൽ = മുകൾ ("above") + ഇൽ. After chillu restoration the stem is മുകൾ,
    # which ends in കൾ, but stripping it would leave മു (1 akshara), so the
    # min-stem floor correctly keeps മുകൾ whole.
    assert segment("മുകളിൽ") == ["മുകൾ", "ഇൽ"]


def test_known_limitation_proper_name_false_split():
    # KNOWN LIMITATION (no lexicon): the name അനിൽ (Anil) ends in the locative
    # surface -ിൽ and clears the 2-akshara floor, so it is wrongly split. Pinned
    # so the limitation is visible; fixing it needs a lexicon/NER (see docstring).
    assert segment("അനിൽ") == ["അൻ", "ഇൽ"]  # stem chillu-restored; still a wrong split of a name


# edge cases: empty input, normalization round-trip

def test_empty_string():
    assert segment("") == [""]


def test_input_is_normalized():
    # Output pieces are normalized; a normalized input round-trips identically.
    word = "വീട്ടിൽ"
    pieces = segment(word)
    assert pieces == [mlnormalize.normalize(p) for p in pieces]
