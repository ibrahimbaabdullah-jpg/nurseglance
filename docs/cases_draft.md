# NurseGlance cases (draft)

Suggested by `etl/select_cases.py`. Replace each summary with your own clinical words.

## S1 — standard

- Stay 36496303 (subject 10005909, admission 20199380), Cardiac Vascular Intensive Care Unit (CVICU)
- Handoff: 2144-10-31 19:00, ICU day 3
- 40 y, F; OBSERVATION ADMIT; principal diagnosis: Acute embolism and thrombosis of left iliac vein
- Died later in this hospital stay: no
- Why standard: no invasive ventilation or vasopressor during the ICU stay; 14 abnormal of 48 lab results in the prior 24 h; 13 heart-rate entries in the prior 12 h
- Swapped in on 2026-11-26 (rank 8 standard candidate). The first-ranked stay, 33846653 (29 F, insulin pump complication), has no eMAR records, so its 12-hour medication timeline was empty.
- Clinical summary (3 lines, your words): ...

## S2 — standard

- Stay 37509585 (subject 10020187, admission 24104168), Neuro Surgical Intensive Care Unit (Neuro SICU)
- Handoff: 2169-01-16 07:00, ICU day 2
- 63 y, F; OBSERVATION ADMIT; principal diagnosis: Nontraumatic subarachnoid hemorrhage from left posterior communicating artery
- Died later in this hospital stay: no
- Why standard: no invasive ventilation or vasopressor during the ICU stay; 7 abnormal of 44 lab results in the prior 24 h; 12 heart-rate entries in the prior 12 h
- Clinical summary (3 lines, your words): ...

## C1 — complex

- Stay 32359580 (subject 10007818, admission 22987108), Medical Intensive Care Unit (MICU)
- Handoff: 2146-06-23 19:00, ICU day 2
- 69 y, M; DIRECT EMER.; principal diagnosis: Other cirrhosis of liver
- Died later in this hospital stay: yes
- Why complex: invasive ventilation and a vasopressor in the 12 h before handoff; 214 abnormal of 326 lab results in the prior 24 h; 24 heart-rate entries in the prior 12 h
- Clinical summary (3 lines, your words): ...

## C2 — complex

- Stay 37093652 (subject 10015931, admission 22130791), Medical/Surgical Intensive Care Unit (MICU/SICU)
- Handoff: 2177-03-26 19:00, ICU day 3
- 88 y, M; URGENT; principal diagnosis: Melena
- Died later in this hospital stay: yes
- Why complex: invasive ventilation and a vasopressor in the 12 h before handoff; 144 abnormal of 269 lab results in the prior 24 h; 10 heart-rate entries in the prior 12 h
- Clinical summary (3 lines, your words): ...
