# mlseg

A rule-based Malayalam surface segmenter. Given an inflected word, it splits it
into a stem plus its case / number suffixes. It is the rough inverse companion to
[`mlinflect`](https://github.com/jayashankarvr/mlinflect) (which generates inflected
forms): `mlseg` takes one apart.

```python
from mlseg import segment

segment("കുട്ടികൾ")        # ['കുട്ടി', 'കൾ']
segment("വീട്ടിൽ")          # ['വീട്', 'ഇൽ']
segment("പുസ്തകങ്ങളിൽ")  # ['പുസ്തകം', 'ങ്ങൾ', 'ഇൽ']
segment("മരം")             # ['മരം']  (no recognised suffix, returned whole)
```

## What it does

`segment(word)` applies a small set of native-ratified surface rules: it strips
a recognised case suffix (locative, sociative, directive, genitive) and a plural
(`കൾ` / `ങ്ങൾ`), reverting the well-known geminate (`…ട്ടി` -> `…ട്`) and
restoring chillu and anusvaram lemmas where the alternation is sound and
reversible. Suffixes come back in their lemma spelling, in surface order (stem
first, outermost suffix last).

## Conservative by construction

This is a best-effort fallback for words a full morphological analyser cannot
handle, not an analyser itself. It splits only on a rule whose surface-to-lemma
realisation has been ratified by a native reviewer. If no rule matches, it
returns the word whole (`[word]`); it never invents a split and never fabricates
Malayalam (no guessed viramas, no fabricated stems). A minimum-stem floor blocks
over-stripping of real words whose tail merely looks like a suffix (മകൾ
"daughter", കോട്ട് "coat"). `segment` is idempotent on bare stems.

## Limitations

There is no lexicon, so a proper name whose tail happens to match a suffix
surface and clears the 2-akshara floor can be false-split, e.g. the name അനിൽ
(Anil) becomes `['അൻ', 'ഇൽ']`. Distinguishing such a name from a true locative
needs a lexicon or NER. Callers that need certainty should prefer a full
analyser; this fills the gap when one is unavailable.

## Install

```bash
pip install mlseg
# from source:
pip install -e ".[dev]"
```

`mlseg` depends on `mlnormalize` for input normalisation, so geminate and chillu
comparisons are byte-stable. It is on PyPI, so `pip install mlseg` pulls it in
automatically.

## License

Apache-2.0. See `LICENSE` and `NOTICE`. Contributions are accepted under Apache-2.0
section 5 (inbound = outbound); no separate CLA is required.

Linguistic sources are credited in `REFERENCES.md`.
