"""Batch evaluation runner for sampled resumes against ground truth.

This script intentionally guards long-running evaluation loops.
By default, run a small smoke sample first; use --confirm-large-run to execute
the full configured sample size.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.evaluation.metrics import RagasEvaluator
from src.rag.retriever import ResumeRetriever


def _load_config() -> dict[str, Any]:
	"""Load project configuration from configs/config.yaml."""
	config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
	with config_path.open("r", encoding="utf-8") as file:
		return yaml.safe_load(file)


@dataclass(slots=True)
class EvaluationRunner:
	"""Coordinate dataset sampling, retrieval, and RAGAS scoring."""

	sample_size: int
	hr_sample_size: int
	it_sample_size: int
	random_seed: int
	resume_csv_path: Path
	report_output_path: Path

	@classmethod
	def from_config(cls) -> "EvaluationRunner":
		"""Build evaluation runner from configuration file."""
		config = _load_config()
		evaluation = config.get("evaluation", {})
		root = Path(__file__).resolve().parents[2]
		csv_path = root / config.get("paths", {}).get("resume_csv", "data/Resume.csv")
		return cls(
			sample_size=int(evaluation.get("sample_size", 30)),
			hr_sample_size=int(evaluation.get("hr_sample_size", 15)),
			it_sample_size=int(evaluation.get("it_sample_size", 15)),
			random_seed=int(evaluation.get("random_seed", 42)),
			resume_csv_path=csv_path,
			report_output_path=root / "data" / "processed" / "evaluation_report.json",
		)

	def run(self, confirm_large_run: bool, smoke_size: int) -> dict[str, Any]:
		"""Run evaluation with optional large-run confirmation.

		Args:
			confirm_large_run: Enables full configured sample size run.
			smoke_size: Number of rows for quick validation mode.

		Returns:
			Summary metrics and run metadata.
		"""
		target_size = self.sample_size if confirm_large_run else smoke_size
		if self.sample_size > smoke_size and not confirm_large_run:
			print(
				"Large run not confirmed. Running smoke test on "
				f"{smoke_size} samples. Use --confirm-large-run for full run."
			)

		rows = self._prepare_rows(target_size)
		retriever = ResumeRetriever.from_config()
		ragas_rows: list[dict[str, Any]] = []

		for row in rows:
			department = row.get("Category", "")
			query = f"Summarize key skills and experience for {row.get('ID', 'candidate')}"
			result = retriever.retrieve(query=query, department=department)
			ragas_rows.append(
				{
					"question": query,
					"reference": row.get("Resume_str", ""),
					"response": result["answer"],
					"retrieved_contexts": result["contexts"],
				}
			)

		scores = RagasEvaluator().evaluate_rows(ragas_rows)
		report = {
			"sample_size": len(ragas_rows),
			"requested_sample_size": target_size,
			"scores": scores,
		}
		self.report_output_path.parent.mkdir(parents=True, exist_ok=True)
		self.report_output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
		return report

	def _prepare_rows(self, total_size: int) -> list[dict[str, Any]]:
		"""Sample approximately balanced rows from HR and IT categories."""
		if not self.resume_csv_path.exists():
			raise FileNotFoundError(f"Resume.csv not found at {self.resume_csv_path}")

		frame = pd.read_csv(self.resume_csv_path)
		random.seed(self.random_seed)

		hr_rows = frame[frame["Category"] == "HR"].to_dict(orient="records")
		it_rows = frame[frame["Category"] == "INFORMATION-TECHNOLOGY"].to_dict(orient="records")

		if total_size == self.sample_size:
			hr_target = min(len(hr_rows), self.hr_sample_size)
			it_target = min(len(it_rows), self.it_sample_size)
		else:
			half = total_size // 2
			hr_target = min(len(hr_rows), half)
			it_target = min(len(it_rows), total_size - hr_target)

		sampled = random.sample(hr_rows, hr_target) + random.sample(it_rows, it_target)
		random.shuffle(sampled)
		return sampled


def parse_args() -> argparse.Namespace:
	"""Parse command line arguments for the evaluation runner."""
	parser = argparse.ArgumentParser(description="Run RAGAS evaluation for resume RAG.")
	parser.add_argument(
		"--confirm-large-run",
		action="store_true",
		help="Run full configured sample size. Without this flag, a smoke test is run.",
	)
	parser.add_argument(
		"--smoke-size",
		type=int,
		default=3,
		help="Number of samples for quick test mode.",
	)
	return parser.parse_args()


if __name__ == "__main__":
	args = parse_args()
	summary = EvaluationRunner.from_config().run(
		confirm_large_run=args.confirm_large_run,
		smoke_size=args.smoke_size,
	)
	print(json.dumps(summary, indent=2))
