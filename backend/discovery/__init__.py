"""Property Discovery — deterministic parcel filter + single-key sort engine.

Design is locked in `claude-context/property-discovery/` (docs 00–09); this package
implements it. The invariant-critical core is registry → cqs/predicates → evaluator:
exactly one function (`evaluator.evaluate`) turns a Canonical Query State into results
(INV-1), and it is a pure function of `(canonical CQS, dataVersion)` (INV-2).
"""
