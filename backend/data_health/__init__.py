"""Data health: a registry of every source the product shows, probes that read each
source's latest data date, and the rules that turn a probe into a status.

``registry`` (what we depend on), ``probes`` (how to read it), ``evaluate`` (pure rules),
``check`` (the CLI). The checker is cheap and dumb: HTTP reads only, no model calls, and
it imports none of the serving stack (no torch, discovery or ``backend.main``).
See ``claude-context/guides/data-health.md``.
"""
