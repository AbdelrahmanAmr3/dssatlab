# API reference

This page documents the public API exported by `dssatlab`. Only names explicitly exported in `dssatlab.__all__` are part of the public interface.

## Discovery and execution

::: dssatlab.connect

::: dssatlab.detect

::: dssatlab.install

::: dssatlab.run

## Simulation, weather, soil, and management

::: dssatlab.Simulation

::: dssatlab.write_weather_template

::: dssatlab.write_soil_template

::: dssatlab.write_management_template

## Treatments and scenarios

::: dssatlab.run_treatments

::: dssatlab.combine_summaries

::: dssatlab.write_scenario_template

## Reading outputs and plotting

::: dssatlab.read_summary

::: dssatlab.read_plant_growth

::: dssatlab.read_soil_water

::: dssatlab.read_plant_nitrogen

::: dssatlab.read_weather

::: dssatlab.to_dataframe

::: dssatlab.plot_plant_growth
    options:
      docstring_options:
        warn_missing_types: false

## Exceptions

::: dssatlab.DSSATError

::: dssatlab.DSSATNotFoundError

::: dssatlab.DSSATInstallError

::: dssatlab.DSSATRunError

::: dssatlab.DSSATOutputError

::: dssatlab.DSSATCheckError
