"""Scoring model, weighted criteria calculations, and run status classification."""

from agentbench.models import BenchmarkTask, CriterionDetail, RunStatus


class Scorer:
    """Computes weighted evaluation scores and classifies execution run statuses."""

    @staticmethod
    def calculate_score(
        results: dict[str, bool],
        weights: dict[str, float] | None = None,
    ) -> float:
        """Calculate weighted score from binary criterion results."""
        if weights is None:
            weights = {
                "configuration": 30.0,
                "startup": 20.0,
                "behavior": 30.0,
                "regression": 20.0,
            }

        earned = sum(
            weight for crit, weight in weights.items() if results.get(crit, False)
        )
        return float(round(earned, 2))

    @staticmethod
    def classify_status(
        score: float,
        pass_threshold: float = 80.0,
        timed_out: bool = False,
        infrastructure_error: bool = False,
        evaluator_error: bool = False,
    ) -> RunStatus:
        """Classify run status separating infrastructure/evaluator failures from agent correctness."""
        if infrastructure_error:
            return RunStatus.INFRASTRUCTURE_ERROR
        if evaluator_error:
            return RunStatus.EVALUATOR_ERROR
        if timed_out:
            return RunStatus.TIMEOUT
        if score >= pass_threshold:
            return RunStatus.PASSED
        if score > 0.0:
            return RunStatus.PARTIAL
        return RunStatus.FAILED

    @staticmethod
    def build_criteria_map(
        task: BenchmarkTask,
        criterion_passes: dict[str, bool],
    ) -> dict[str, CriterionDetail]:
        """Construct structured criterion details according to task scoring weights."""
        weights = {
            "configuration": task.scoring.configuration,
            "startup": task.scoring.startup,
            "behavior": task.scoring.behavior,
            "regression": task.scoring.regression,
        }

        criteria_map: dict[str, CriterionDetail] = {}
        for crit, weight in weights.items():
            passed = bool(criterion_passes.get(crit, False))
            criteria_map[crit] = CriterionDetail(
                weight=weight,
                passed=passed,
                score=weight if passed else 0.0,
                details=f"{crit.capitalize()} {'satisfied' if passed else 'failed'}",
            )
        return criteria_map
