from typing import List, Optional
import numpy as np
import pandas as pd
from backend.app.schemas.common import SimulationTypeEnum
from backend.app.schemas.experiment import SimulationParameters
from backend.app.services.dataset_service import classify_dtype


def apply_drift_simulation(
    df: pd.DataFrame,
    params: SimulationParameters,
) -> pd.DataFrame:
    """Apply deterministic, controlled synthetic drift perturbation to a DataFrame copy."""
    if params.simulation_type == SimulationTypeEnum.NONE:
        return df.copy()

    sim_df = df.copy()
    rng = np.random.RandomState(params.seed)

    # Determine eligible features
    candidate_cols = params.target_features if params.target_features else list(sim_df.columns)

    if params.simulation_type == SimulationTypeEnum.MEAN_SHIFT:
        for col in candidate_cols:
            if col in sim_df.columns and classify_dtype(sim_df[col]) == "numeric":
                series = pd.to_numeric(sim_df[col], errors="coerce")
                std_val = float(series.std()) if float(series.std()) > 0 else 1.0
                shift = params.magnitude * std_val
                sim_df[col] = series + shift

    elif params.simulation_type == SimulationTypeEnum.VARIANCE_SCALE:
        scale_factor = max(0.1, min(10.0, params.magnitude))
        for col in candidate_cols:
            if col in sim_df.columns and classify_dtype(sim_df[col]) == "numeric":
                series = pd.to_numeric(sim_df[col], errors="coerce")
                mean_val = float(series.mean())
                sim_df[col] = mean_val + (series - mean_val) * scale_factor

    elif params.simulation_type == SimulationTypeEnum.CATEGORICAL_SHIFT:
        for col in candidate_cols:
            if col in sim_df.columns and classify_dtype(sim_df[col]) in ("categorical", "boolean"):
                cats = sim_df[col].dropna().unique().tolist()
                if len(cats) >= 2:
                    # Randomly perturb a fraction of the rows based on magnitude
                    perturb_rate = min(0.9, params.magnitude * 0.15)
                    mask = rng.rand(len(sim_df)) < perturb_rate
                    sim_df.loc[mask, col] = rng.choice(cats, size=mask.sum())

    elif params.simulation_type == SimulationTypeEnum.MISSING_VALUES:
        missing_rate = min(0.85, max(0.05, params.magnitude * 0.1))
        for col in candidate_cols:
            if col in sim_df.columns:
                mask = rng.rand(len(sim_df)) < missing_rate
                sim_df.loc[mask, col] = np.nan

    elif params.simulation_type == SimulationTypeEnum.GRADUAL_DRIFT:
        n_rows = len(sim_df)
        linear_weights = np.linspace(0.0, 1.0, n_rows)
        for col in candidate_cols:
            if col in sim_df.columns and classify_dtype(sim_df[col]) == "numeric":
                series = pd.to_numeric(sim_df[col], errors="coerce")
                std_val = float(series.std()) if float(series.std()) > 0 else 1.0
                max_shift = params.magnitude * std_val
                sim_df[col] = series + (linear_weights * max_shift)

    return sim_df
