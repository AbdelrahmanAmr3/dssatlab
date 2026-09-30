"""Small statistics for checked evaluation pairs, in DSSAT units or days."""

import math

from .outputs import _SUMMARY_DATES, _date_value


def _rmse(errors):
    return math.sqrt(sum(error ** 2 for error in errors) / len(errors))


def _bias(errors):
    return sum(errors) / len(errors)


def _d_index(observed, simulated):
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
            observed = [_date_value(variable, str(value)).toordinal() for value in observed]
            simulated = [_date_value(variable, str(value)).toordinal() for value in simulated]
        errors = [row["error"] for row in rows]
        statistics[variable] = dict(n=len(rows), rmse=_rmse(errors), bias=_bias(errors),
                                    d_index=_d_index(observed, simulated))
    return statistics
