# V&V reporting: software verification is not physical validation

The original M7 report contained an ambiguous legacy key
`validated_vs_assumed.validated` that listed analytical dynamics checks,
manufacturer bench-table readback, and software full-throttle chain
reproduction. These are **numerical/software verification results**, not
independent physical prediction validation.

The report now preserves a backward-compatible `validated` key with an
empty value and moves those entries into `verified_in_software`. The
rendered Markdown explicitly states:

- Software verification gate results are not certification.
- **Independent physical validation: NOT ESTABLISHED.**
- **Decision-equivalent to physical testing: NO.**
- Independent physical-validation evidence, operating limits, sensor
  uncertainties and frozen blind holdouts remain necessary.

The existing `needs_further_analysis` flag continues to describe the
**software/numerical regression gate only**. Passing that gate does not
turn off `needs_independent_physical_validation`, which stays true until
externally traceable evidence and independently reviewed decision criteria
are actually provided.

This revision does **not** change the underlying numerical models,
simulation predictions, benchmarks, CI thresholds or source data.
The primary scientific objective remains near-real-world model accuracy
within measured, preregistered operating envelopes—not blanket replacement
of real-world experiments.

Related physical-evidence blockers: #16, #21, #23, #25, #27 and #28.
