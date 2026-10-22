import numpy as np
import pandas as pd
from pathlib import Path

out_dir = Path("c:/OMNIVEX/data/demo")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. Reference Dataset (200 rows)
rng = np.random.RandomState(42)
n_ref = 250
age = rng.randint(21, 65, size=n_ref)
income = rng.normal(65000, 15000, size=n_ref).clip(20000, 150000)
credit_score = rng.normal(700, 50, size=n_ref).clip(500, 850)
dti = rng.uniform(0.1, 0.6, size=n_ref)
emp = rng.choice(["Salaried", "Self-Employed", "Contract", "Govt"], size=n_ref, p=[0.5, 0.2, 0.15, 0.15])

# Logistic function for ground truth default risk
z = -3.5 + 0.03 * (60 - age) - 0.00003 * income - 0.008 * (credit_score - 600) + 3.0 * dti
prob = 1.0 / (1.0 + np.exp(-z))
loan_default = (rng.rand(n_ref) < prob).astype(int)

ref_df = pd.DataFrame({
    "age": age,
    "annual_income": np.round(income, 2),
    "credit_score": np.round(credit_score, 1),
    "debt_to_income": np.round(dti, 3),
    "employment_type": emp,
    "loan_default": loan_default,
})
ref_df.to_csv(out_dir / "reference_credit_risk.csv", index=False)

# 2. Incoming Baseline Stable (100 rows, same distribution)
rng_stable = np.random.RandomState(101)
n_inc = 120
s_age = rng_stable.randint(21, 65, size=n_inc)
s_income = rng_stable.normal(65000, 15000, size=n_inc).clip(20000, 150000)
s_credit_score = rng_stable.normal(700, 50, size=n_inc).clip(500, 850)
s_dti = rng_stable.uniform(0.1, 0.6, size=n_inc)
s_emp = rng_stable.choice(["Salaried", "Self-Employed", "Contract", "Govt"], size=n_inc, p=[0.5, 0.2, 0.15, 0.15])
s_z = -3.5 + 0.03 * (60 - s_age) - 0.00003 * s_income - 0.008 * (s_credit_score - 600) + 3.0 * s_dti
s_prob = 1.0 / (1.0 + np.exp(-s_z))
s_default = (rng_stable.rand(n_inc) < s_prob).astype(int)

stable_df = pd.DataFrame({
    "age": s_age,
    "annual_income": np.round(s_income, 2),
    "credit_score": np.round(s_credit_score, 1),
    "debt_to_income": np.round(s_dti, 3),
    "employment_type": s_emp,
    "loan_default": s_default,
})
stable_df.to_csv(out_dir / "incoming_baseline_stable.csv", index=False)

# 3. Incoming Drifted (severe income drop & credit score shock)
rng_drift = np.random.RandomState(202)
d_age = rng_drift.randint(21, 65, size=n_inc)
d_income = rng_drift.normal(42000, 10000, size=n_inc).clip(15000, 80000)  # Major drop
d_credit_score = rng_drift.normal(610, 45, size=n_inc).clip(450, 750)     # Score drop
d_dti = rng_drift.uniform(0.35, 0.85, size=n_inc)                         # Debt surge
d_emp = rng_drift.choice(["Salaried", "Self-Employed", "Contract", "Govt"], size=n_inc, p=[0.25, 0.45, 0.25, 0.05])
d_z = -3.5 + 0.03 * (60 - d_age) - 0.00003 * d_income - 0.008 * (d_credit_score - 600) + 3.0 * d_dti
d_prob = 1.0 / (1.0 + np.exp(-d_z))
d_default = (rng_drift.rand(n_inc) < d_prob).astype(int)

drift_df = pd.DataFrame({
    "age": d_age,
    "annual_income": np.round(d_income, 2),
    "credit_score": np.round(d_credit_score, 1),
    "debt_to_income": np.round(d_dti, 3),
    "employment_type": d_emp,
    "loan_default": d_default,
})
drift_df.to_csv(out_dir / "incoming_drift_economic_shock.csv", index=False)

# 4. Incoming Unlabelled Batch (Production real-time streaming batch)
unlabelled_df = drift_df.drop(columns=["loan_default"])
unlabelled_df.to_csv(out_dir / "incoming_unlabelled_stream.csv", index=False)

print("Demo datasets generated successfully in data/demo/")
