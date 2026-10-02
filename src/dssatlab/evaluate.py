"""Observed data checks and comparison with Summary and Plant growth (ADR 0007)."""

from dataclasses import dataclass
import math

from .errors import DSSATCheckError, DSSATOutputError
from .outputs import _SUMMARY_DATES, to_dataframe
from .runner import RunResult
from .observed import _KEYS, _load_observed


@dataclass(frozen=True)
class Evaluation:
    """Measured/simulated pairs and statistics by variable (ticket #95).

    Each pair has scenario, treatment, date, variable, observed, simulated and
    error. Dates use YYYYDDD codes; Summary pairs have date=None. Date errors,
    RMSE and bias are in days. Other values retain DSSAT's units. Statistics
    contain n, rmse, bias and d_index only for variables with at least two pairs.
    """

    pairs: list[dict]
    statistics: dict[str, dict]

    def __repr__(self) -> str:
        variables = list(dict.fromkeys(pair["variable"] for pair in self.pairs))
        return f"Evaluation({len(self.pairs)} pairs, variables={variables!r})"

    def to_dataframe(self):
        """Return the pairs as a DataFrame, importing pandas only when called."""
        return to_dataframe(self.pairs)


def evaluate(results: RunResult | dict[tuple[str, int], RunResult], observed) -> Evaluation:
    """Compare a run or run_treatments() results with observed measurements.

    Accept a CSV path, DataFrame, or list of dicts. A single
    run uses scenario 'base' and the TRNO values in its Summary. Match Summary
    by treatment, Plant growth by treatment and YEAR/DOY. Check every requested
    pair before computing errors; observed and matching/output problems raise a single
    DSSATCheckError. Unobserved results are ignored. Pair order follows observed
    rows and their measurement columns; statistics pool each variable's pairs.
    """
    observed, problems = _load_observed(observed)
    results, cache = _results_by_key(results, problems)
    pairs = []
    for row in observed:
        scenario, treatment, day = row["scenario"], row["treatment"], row["date"]
        where = f"Scenario {scenario!r}, treatment {treatment}, date {_date_code(day) if day else None}"
        result = results.get((scenario, treatment))
        if result is None:
            problems.append(f"{where}: no matching result. Check the observed keys "
                            "against the supplied results.")
            continue
        daily = day is not None
        filename = "PlantGro.OUT" if daily else "Summary.OUT"
        simulated = _simulated_row(result, treatment, day, cache, where, problems)
        if simulated is None:
            continue
        for variable, measured in row.items():
            if variable in _KEYS:
                continue
            if variable not in simulated:
                problems.append(f"{where}, {variable}: variable absent from {filename}. "
                                "Check the measurement column against the simulated output.")
            elif simulated[variable] is None or simulated[variable] == -99:
                problems.append(f"{where}, {variable}: simulated value is missing (-99) "
                                f"in {filename}. Check the run inputs and rerun DSSAT.")
            else:
                pairs.append(dict(scenario=scenario, treatment=treatment, date=day,
                                  variable=variable, observed=measured,
                                  simulated=simulated[variable]))
    if problems:
        raise DSSATCheckError(problems)
    for pair in pairs:
        simulated, measured = pair["simulated"], pair["observed"]
        if pair["variable"] in _SUMMARY_DATES:
            pair["error"] = (simulated - measured).days
        else:
            pair["error"] = simulated - measured
    statistics = _statistics(pairs)
    for pair in pairs:
        if pair["date"] is not None:
            pair["date"] = _date_code(pair["date"])
        if pair["variable"] in _SUMMARY_DATES:
            for name in ("observed", "simulated"):
                pair[name] = _date_code(pair[name])
    return Evaluation(pairs, statistics)


def _results_by_key(results, problems):
    """Map a single run's Summary treatments to 'base', retaining its read cache."""
    cache = {}
    if isinstance(results, RunResult):
        try:
            summary = results.summary()
        except DSSATOutputError as error:
            problems.append(f"Scenario 'base': {error}")
            summary = []
        cache[results.run_dir, False] = summary
        results = {("base", row["TRNO"]): results for row in summary}
    return results, cache


def _simulated_row(result, treatment, day, cache, where, problems):
    """Find one simulated row, collecting output and matching problems."""
    daily = day is not None
    filename = "PlantGro.OUT" if daily else "Summary.OUT"
    key = (result.run_dir, daily)
    if key not in cache:
        try:
            cache[key] = result.plant_growth() if daily else result.summary()
        except DSSATOutputError as error:
            cache[key] = None
            problems.append(f"{where}: {error}")
    if cache[key] is None:
        return None
    matches = [sim for sim in cache[key] if sim["TRNO"] == treatment
               and (not daily or (sim["YEAR"], sim["DOY"]) == divmod(_date_code(day), 1000))]
    if len(matches) != 1:
        detail = "no simulated row" if not matches else "multiple simulated rows"
        problems.append(f"{where}: {detail} in {filename}. "
                        "Supply output with one matching treatment/date row.")
        return None
    return matches[0]


def _date_code(day):
    """Convert a calendar date to DSSAT's yyyyddd integer."""
    return day.year * 1000 + day.timetuple().tm_yday


def _rmse(errors):
    return math.sqrt(sum(error ** 2 for error in errors) / len(errors))


def _bias(errors):
    return sum(errors) / len(errors)


def _d_index(observed, simulated):
    """Willmott index; zero denominator gives 1 for zero error, otherwise 0."""
    mean = sum(observed) / len(observed)
    numerator = sum((sim - obs) ** 2 for obs, sim in zip(observed, simulated))
    denominator = sum((abs(sim - mean) + abs(obs - mean)) ** 2
                      for obs, sim in zip(observed, simulated))
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
    return 1 - numerator / denominator


def _statistics(pairs):
    grouped, statistics = {}, {}
    for pair in pairs:
        grouped.setdefault(pair["variable"], []).append(pair)
    for variable, rows in grouped.items():
        if len(rows) < 2:
            continue
        observed = [row["observed"] for row in rows]
        simulated = [row["simulated"] for row in rows]
        if variable in _SUMMARY_DATES:
            observed = [value.toordinal() for value in observed]
            simulated = [value.toordinal() for value in simulated]
        errors = [row["error"] for row in rows]
        statistics[variable] = dict(n=len(rows), rmse=_rmse(errors), bias=_bias(errors),
                                    d_index=_d_index(observed, simulated))
    return statistics
