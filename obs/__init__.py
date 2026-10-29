# SPDX-License-Identifier: BSD-3-Clause

"""可观测层：trace 泵 + 聚合 reader（四壳共享，见 DESIGN_observability.md）。"""

from .jsonl import FileTraceSink, aggregate, read_traces

__all__ = ["FileTraceSink", "aggregate", "read_traces"]