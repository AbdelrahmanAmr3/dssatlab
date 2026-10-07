"""Observed data checks and comparison with Summary and Plant growth (ADR 0007)."""

from dataclasses import dataclass, field
import math

from .errors import DSSATCheckError, DSSATOutputError
from .outputs import _SUMMARY_DATES, to_dataframe
from .runner import RunResult
from .observed import (_KEYS, _PLANT_COLUMNS, _SUMMARY_COLUMNS,
                       _check_measurements, _load_observed, _unknown)


@dataclass(frozen=True)
class Evaluation:
    """Measured/simulated pairs and statistics by variable (ticket #95).

    Each pair has scenario, treatment, date, variable, observed, simulated and
    error. Dates use YYYYDDD codes; Summary pairs have date=None. Date errors,
    RMSE and bias are in days. Other values retain DSSAT's units. Statistics
    contain n, rmse, bias and d_index only for variables with at least two pairs.
    excluded lists observed rows before the first or after the last Plant growth
    day for their scenario and treatment. Each has scenario, treatment, date
    (YYYYDDD) and a reason naming the simulated boundary. Their measurements
    are not checked and do not contribute to pairs or statistics.
    """

    pairs: list[dict]
    statistics: dict[str, dict]
    excluded: list[dict] = field(default_factory=list)

    def __repr__(self) -> str:
        variables = list(dict.fromkeys(pair["variable"] for pair in self.pairs))
        excluded = f"{len(self.excluded)} excluded, " if self.excluded else ""
        return f"Evaluation({len(self.pairs)} pairs, {excluded}variables={variables!r})"

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
    Daily rows outside their scenario/treatment's simulated range are listed in
    excluded without checking their measurements. Interior missing dates, empty
    Plant growth and an evaluation with every row excluded raise DSSATCheckError.
    """
    observed, problems = _load_observed(observed, check_measurements=False)
    results, cache = _results_by_key(results, problems)
    pairs, excluded, unknown = [], [], set()
    for row in observed:
        scenario, treatment, day = row["scenario"], row["treatment"], row["date"]
        where = f"Scenario {scenario!r}, treatment {treatment}, date {_date_code(day) if day else None}"
        result = results.get((scenario, treatment))
        if result is None:
            problems.append(f"{where}: no matching result. Check the observed keys "
                            "against the supplied results.")
        daily = day is not None
        filename = "PlantGro.OUT" if daily else "Summary.OUT"
        count = len(excluded)
        simulated = (_simulated_row(result, scenario, treatment, day, cache, where,
                                    problems, excluded) if result is not None else None)
        if len(excluded) != count:
            continue
        for name in row:
            if name not in _KEYS | _SUMMARY_COLUMNS | _PLANT_COLUMNS and name not in unknown:
                problems.append(_unknown(name))
                unknown.add(name)
        measurements = _check_measurements(row, daily, where, problems)
        if simulated is None:
            continue
        for variable, measured in measurements.items():
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
    if excluded and len(excluded) == len(observed):
        problems.append("Cannot evaluate observed data: every row is outside its scenario and "
                        "treatment's Plant growth date range. Supply observations within the "
                        "simulated range or rerun DSSAT to cover the observed dates.")
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
    return Evaluation(pairs, statistics, excluded)


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


def _simulated_row(result, scenario, treatment, day, cache, where, problems, excluded):
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
    rows = [sim for sim in cache[key] if sim["TRNO"] == treatment]
    dates = [sim["DATE"] for sim in rows if sim["DATE"] is not None] if daily else []
    if dates:
        first, last = min(dates), max(dates)
        if day < first or day > last:
            boundary, label = (first, "before the first") if day < first else (last, "after the last")
            excluded.append(dict(scenario=scenario, treatment=treatment, date=_date_code(day),
                                 reason=f"{label} simulated day {boundary.isoformat()} "
                                        f"({_date_code(boundary)})"))
            return None
    matches = [sim for sim in rows
               if not daily or (sim["YEAR"], sim["DOY"]) == divmod(_date_code(day), 1000)]
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
