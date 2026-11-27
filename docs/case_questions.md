# Handoff questions (draft)

Generated from `docs/case_questions.json`, which study mode reads. **Draft:** review each question and answer key in your own clinical words. Q1-Q3 are scored automatically (exact, or within the tolerance); Q4 is scored 0-2 with the rubric.

**For the clinical reviewers.** The three Rising/Falling/Stable trend questions compare the latest value with the value 12 hours before handoff, and all three keys are Falling. Change one to a question whose key is Rising or Stable (for example C2's fentanyl rate, 30 mcg/h 12 hours before handoff and 40 mcg/h now), so that a participant who always answers Falling cannot score 3 of 3.

## S1

**S1-Q1 (lookup).** What is the most recent potassium?
- Answer: **3.2 mEq/L** ± 0.05
- Source: Lab 50971 at 02:15 (below the 3.3 reference limit)
- Data elements: potassium

**S1-Q2 (trend).** Compared with 12 hours before handoff, is the heart rate now rising, falling or stable?
- Answer: **Falling** (options: Rising, Falling, Stable)
- Source: Range 71-98 bpm over 12 h; latest 81 bpm, down 16 from 12 h earlier
- Data elements: heart_rate

**S1-Q3 (timing).** At what time is the next oxycodone dose given after handoff?
- Answer: **21:37** ± 30 min
- Source: eMAR: oxycodone 5 mg given 21:37 (next 12 h used as a stand-in for due)
- Data elements: med_administrations

**S1-Q4 (synthesis).** What is your top safety concern for the next 12 hours, and what data support it?
- 2 points: Names bleeding risk on the heparin infusion after a vascular procedure complication, with at least one supporting value (Hgb 9.3, platelets 146, the procedure-related diagnosis codes), or names hypokalemia (K 3.2) with its value and the need to replace and recheck.
- 1 points: Names a relevant concern (bleeding, anticoagulation, low potassium, pain control) without supporting data.
- 0 points: No concern, or one not supported by this patient's data.
- Data elements: hemoglobin, platelets, potassium, diagnoses, infusions

## S2

**S2-Q1 (lookup).** What is the most recent GCS total?
- Answer: **15 points**
- Source: Eye + verbal + motor at 06:00
- Data elements: gcs_total

**S2-Q2 (trend).** What was the lowest MAP in the last 12 hours?
- Answer: **63 mmHg** ± 1
- Source: MAP range 63-97 mmHg over 12 h (arterial line first, then cuff)
- Data elements: map

**S2-Q3 (timing).** At what time is the next nimodipine dose given after handoff?
- Answer: **10:50** ± 30 min
- Source: eMAR: nimodipine 30 mg x2 at 10:50, then 14:24
- Data elements: med_administrations

**S2-Q4 (synthesis).** What is your top safety concern for the next 12 hours, and what data support it?
- 2 points: Names neurological decline after subarachnoid hemorrhage (vasospasm or rebleed) and the need for close neuro checks or blood pressure control, with supporting data (GCS 15 now and 14 at its lowest, MAP dipped to 63, nimodipine can lower BP, levetiracetam for seizure prophylaxis).
- 1 points: Names a relevant concern without supporting data.
- 0 points: No concern, or one not supported by this patient's data.
- Data elements: gcs_total, map, pupils, med_administrations

## C1

**C1-Q1 (lookup).** What is the current norepinephrine rate?
- Answer: **0.2 mcg/kg/min** ± 0.01
- Source: Rate since 17:19 (0.4 twelve hours earlier)
- Data elements: vasoactive_drips

**C1-Q2 (trend).** Compared with 12 hours before handoff, is the lactate now rising, falling or stable?
- Answer: **Falling** (options: Rising, Falling, Stable)
- Source: Lactate 9.0 at its highest, 4.3 at 17:41
- Data elements: lactate

**C1-Q3 (timing).** At what time is the next vancomycin dose given after handoff?
- Answer: **01:01** ± 30 min
- Source: eMAR: vancomycin 1000 mg at 01:01
- Data elements: med_administrations

**C1-Q4 (synthesis).** What is your top safety concern for the next 12 hours, and what data support it?
- 2 points: Names hemodynamic instability (MAP 64, below 65, on norepinephrine and vasopressin) with one more supporting value (lactate 4.3, urine 10 mL in 6 h on CRRT, net +3.2 L), or names bleeding risk with values (Hgb 7.2, platelets 38, INR 1.8).
- 1 points: Names a relevant concern without supporting data.
- 0 points: No concern, or one not supported by this patient's data.
- Data elements: map, vasoactive_drips, lactate, urine_output_6h, net_12h, hemoglobin, platelets, inr

## C2

**C2-Q1 (lookup).** What is the current heart rate?
- Answer: **130 bpm** ± 2
- Source: Heart rate at 19:00; rhythm AF
- Data elements: heart_rate

**C2-Q2 (trend).** Compared with 12 hours before handoff, is the norepinephrine rate now rising, falling or stable?
- Answer: **Falling** (options: Rising, Falling, Stable)
- Source: 0.20 mcg/kg/min twelve hours earlier, 0.04 since 18:24
- Data elements: vasoactive_drips

**C2-Q3 (timing).** At what time is the next cefepime dose given after handoff?
- Answer: **01:41** ± 30 min
- Source: eMAR: cefepime 1 g at 01:41
- Data elements: med_administrations

**C2-Q4 (synthesis).** What is your top safety concern for the next 12 hours, and what data support it?
- 2 points: Names ongoing GI bleeding (melena; Hgb down from 9.6 to 7.9; platelets 68) or atrial fibrillation with a rapid rate (HR 130) in a patient still on vasopressors, with supporting values; credit for noting DNR status.
- 1 points: Names a relevant concern without supporting data.
- 0 points: No concern, or one not supported by this patient's data.
- Data elements: hemoglobin, platelets, heart_rate, heart_rhythm, vasoactive_drips, code_status
