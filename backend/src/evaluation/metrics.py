"""Metric helpers for context precision and answer correctness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import answer_correctness, context_precision


@dataclass(slots=True)
class RagasEvaluator:
	"""Evaluate RAG quality with context precision and answer correctness."""

	def evaluate_rows(self, rows: list[dict[str, Any]]) -> dict[str, float]:
		"""Run RAGAS metrics on rows and return mean scores.

		Args:
			rows: List containing `question`, `reference`, `response`,
				and `retrieved_contexts`.

		Returns:
			Dictionary with aggregated metric values.
		"""
		if not rows:
			return {"context_precision": 0.0, "answer_correctness": 0.0}

		dataset = Dataset.from_list(rows)
		result = evaluate(dataset=dataset, metrics=[context_precision, answer_correctness])
		return {
			"context_precision": float(result["context_precision"]),
			"answer_correctness": float(result["answer_correctness"]),
		}
