# Research question 1: can FHIR supply what ICU nurses need at handoff?

**Answer:** almost all of it can be mapped, but not all of it arrives usable. 57 of 58 nurse
handoff data elements (98%) have a source in the MIMIC-IV Clinical Database Demo on FHIR
v2.1.0. For the 4 study cases, 66% (standard cases) and 84% (complex cases) of elements
had a value in the handoff window. The FHIR files hold exactly the same rows as the CSV demo
for every element's items. The gaps come from what the source data never captured, from
coded text lost in conversion, and from local codes with no standard terminology attached.

Produced by `etl/coverage.py` (`docs/coverage.csv`) and the checks described below.
Run on 2026-11-26.

## Coverage by organ system

"Mappable" means the element has a source in the FHIR demo files. The case columns show the
share of elements with at least one value in that case's window (24 h before handoff; 72 h
for labs).

| Organ system | Elements | Mappable | S1 | S2 | C1 | C2 |
| --- | --- | --- | --- | --- | --- | --- |
| Neuro | 7 | 100% | 86% | 86% | 86% | 100% |
| CV | 8 | 100% | 62% | 50% | 88% | 75% |
| Resp | 10 | 100% | 40% | 30% | 100% | 100% |
| Renal/I&O | 12 | 100% | 92% | 92% | 100% | 92% |
| GI/Nutrition | 6 | 100% | 50% | 50% | 50% | 50% |
| Heme/ID | 6 | 100% | 83% | 83% | 83% | 100% |
| Skin/Lines/Devices | 4 | 100% | 75% | 100% | 100% | 100% |
| Safety | 5 | 80% | 20% | 40% | 40% | 40% |
| **All** | **58** | **98%** | **66%** | **66%** | **84%** | **84%** |

Many empty cells are expected: a patient who is not ventilated has no PEEP, and standard
cases have no vasopressors. Those are true negatives, not data gaps. The lower Resp and CV
coverage of S1 and S2 reflects that.

## FHIR completeness against the CSV demo

For each element's MIMIC item IDs, the number of records in the whole demo (100 patients)
is identical in the FHIR files and the CSV tables, for all 49 elements that come from a
single source table. Sampled values also match on value, item and time (`tests/test_fhir_vs_csv.py`).
At the row level, the conversion lost nothing.

## Gaps and their causes

| Gap | Elements | Cause | Type | What NurseGlance does |
| --- | --- | --- | --- | --- |
| No allergy data | Allergies | The demo has no AllergyIntolerance resource; MIMIC-IV has no allergy table | Not captured in source | Shows "not in FHIR demo" |
| No nursing narrative notes | (handoff context, plan of care) | Notes are in MIMIC-IV-Note, a separate credentialed dataset | Not in the open data | Not shown; stated as a limitation |
| Coded text lost | Ventilator mode, pain level, CAM-ICU | FHIR v2.1.0 carries MIMIC's numeric code (ventilator mode "CMV/ASSIST/AutoFlow" arrives as 49) and drops the charted text | Conversion defect | Restores text from `docs/value_codes.csv` (40 code-text pairs, 10 items), built from the CSV demo |
| No standard codes | All chart and lab items | MIMIC-IV on FHIR codes items in MIMIC's own code systems; LOINC appears only on ED vital signs | Terminology | `docs/loinc_mapping.csv` maps 50 items to LOINC, each checked against NLM |
| Old LOINC map unreliable | 5 labs | MIMIC-IV v1.0 supplied lab LOINC codes, but 2 are deprecated (glucose 6777-7, INR 5895-7), 1 does not fit the unit (magnesium in mg/dL coded as moles), 1 names a manual WBC count, and the 5 blood-gas items have none | Terminology | Replaced and documented in the mapping table |
| Code status rarely charted | Code status | Charted for few stays (162 rows in the demo) and not in any study case's window | Documentation practice | For C2, shows DNR from the billing diagnosis Z66 and labels it as such |
| No medication schedule | Due medications, 12-hour timeline | MIMIC records doses given (eMAR), not doses scheduled | Not captured in source | Uses doses given in the next 12 h as a stand-in, and says so |
| eMAR missing for some admissions | Medication timeline | Only 85 of the demo's 140 ICU stays belong to admissions with any eMAR rows | Not captured in source | Cases were checked for eMAR data; S1 was swapped for this reason |
| Medications split across two sources | Insulin, antibiotics | ICU input events and the hospital eMAR record different doses (C2's subcutaneous insulin is only in the eMAR) | Source fragmentation | Timeline uses the eMAR; organ panels use ICU input events; a known inconsistency |
| No pending orders or results | Pending labs | Orders are in provider order entry (POE), which the demo converts only in part | Not converted | Virtual-nurse checklist shows the time of the last results instead |
| Rarely charted | Stool output (19 rows), mechanical circulatory support (40), precautions (64) | Low documentation or rare in a 100-patient sample | Sample size | Shown as "not charted" when absent |

Two starter item lists were corrected during this analysis: fall risk now uses the six
Morse Fall Scale items (summed, LOINC 59460-6), and restraints use the non-violent restraint
items (227945, 227948). The earlier IDs had no rows anywhere in the demo.

## Limitations

The demo is 100 patients from one academic center in Boston, with dates shifted into the
future. Coverage was measured on 4 cases, chosen to contrast standard and complex care, so
the per-case percentages describe these cases, not ICU stays in general.
