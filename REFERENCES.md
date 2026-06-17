# References

`mlseg` implements Malayalam morphological **facts** (case-marker allomorphy,
geminate reversion, chillu and anusvaram restoration) restated in our own code.
**No text, tables, code, or datasets from any source below are reproduced or
redistributed.** These citations are scholarly credit; they imply no endorsement
and create no license obligation.

The surface rules are native-ratified: each split the segmenter performs was
signed off through a native-reviewer workflow before being added.

## Sources

- **`native-review-2`**: Native-reviewer ratification (correctness log, item #2):
  geminate reversion (`…ട്ടി` -> `…ട്`) before the locative and directive, e.g.
  വീട്ടിൽ -> [വീട്, ഇൽ], നാട്ടിലേക്ക് -> [നാട്, ലേക്ക്].
- **`native-review-3`**: Native-reviewer ratification (correctness log, item #3):
  anusvaram restoration on `ങ്ങൾ` plurals, e.g. പുസ്തകങ്ങളിൽ ->
  [പുസ്തകം, ങ്ങൾ, ഇൽ], and the conservative chillu-lemma restoration applied on
  every case branch.
- **`smc-morph`**: SMC's Malayalam morphology documentation, covering nominal
  inflection rules (https://morph.smc.org.in/ninfl/cases.html). Used as the
  factual backbone for the case-suffix surface forms. Rules restated as facts,
  no data copied.
