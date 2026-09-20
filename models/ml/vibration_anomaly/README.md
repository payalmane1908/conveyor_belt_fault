# Condition-Aware Vibration Anomaly Detector (Phase 4A)

## 1. What It Does
* **Task:** Condition-Aware Vibration Anomaly Detection.
* **Architecture:** Scikit-learn `IsolationForest` (100 estimators) operating on `RobustScaler`-standardized 10-dimensional feature vectors.
* **Condition-Aware Input:** Inputs motor rotational speed (`speed_rpm`) and static tension (`pretension_n`) alongside 8 multi-axis DSP vibration features (`driver_rms`, `driver_peak`, `driver_crest_factor`, `driver_kurtosis`, `driver_dominant_freq_hz`, `driven_rms`, `driven_crest_factor`, `driven_dominant_freq_hz`).
* **Inference Output:** Continuous raw anomaly score and binary anomaly decision (`decision_function < 0`).

## 2. What It Does NOT Do (Domain Limitations)
> [!IMPORTANT]
> * **NO CONVEYOR JOINT RUPTURE PREDICTION:** This model is trained on a laboratory belt-drive test rig (G.U.N.T PT 500.14). It does NOT predict vulcanized or mechanical conveyor splice pullout or joint separation in mining fields.
> * **NO SAFETY SHUTDOWN OVERRIDE:** This model acts as an independent evidence source in the Multi-Evidence Joint Passport. It does NOT directly trigger automated emergency trips (`TRIP`).
> * **NO PROBABILITY CLAIMS:** The score is a non-parametric tree-isolation metric, NOT a calibrated percentage probability of failure.

## 3. Dataset & Provenance
* **Dataset:** Experimental vibration data for a belt drive system under different operating conditions.
* **Mendeley DOI:** [10.17632/jf8v2ndydr.1](https://doi.org/10.17632/jf8v2ndydr.1)
* **Publication DOI:** [10.1016/j.dib.2023.109156](https://doi.org/10.1016/j.dib.2023.109156)
* **License:** CC BY 4.0

## 4. Training Population
* **Total Training Runs:** 102 runs.
* **Filter:** Strictly `fault_code == 'NORMAL'` (Healthy, balanced belt) from Repetitions 1 and 2 across all 17 speeds (400–2000 RPM) and 3 tensions (70, 110, 150 N).
* **Synthetic Data Contamination:** 0.0% (Zero synthetic simulation samples used).

## 5. Frozen Evaluation Results (357 Unseen Runs)
* **ROC-AUC:** 0.6995
* **PR-AUC:** 0.9263
* **Precision:** 0.9153
* **Recall:** 0.5654
* **F1-Score:** 0.6990
* **Specificity:** 0.6863
* **False Positive Rate:** 0.3137
* **Statistical Baseline Comparison:** Outperforms Euclidean distance baseline by +0.0580 ROC-AUC.
