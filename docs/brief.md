# NurseGlance: one screen for ICU nurse handoff

**Ibrahim Baabdallah** · applicant, PhD in Health Informatics, UNC Chapel Hill (fall 2027) · November 2026<br>
Live demo: [nurseglance on Streamlit](https://ibrahimbaabdullah-jpg-nurseglance-streamlit-app-uvwgbm.streamlit.app/) ·
Code and reports: [github.com/ibrahimbaabdullah-jpg/nurseglance](https://github.com/ibrahimbaabdullah-jpg/nurseglance) ·
Research prototype, not for clinical use.

**Problem.** ICU nurses check the EHR at every handoff, and the values they need sit in
different tabs. In a survey of 107 ICU nurses about handoff, 64% said current EHR
visualization was insufficient and 53% wanted screens organized by organ system (Lindroth
et al. 2022).
Visualization dashboards such as AWARE are being tested with ICU physicians and advanced
practice providers (Khairat et al. 2025a). Nurses need different things: drips and their
titration, lines and devices, intake and output, the medication schedule and safety risks.

**What I built, on open data.**

- A FHIR R4 pipeline over the MIMIC-IV demo on FHIR: 58 nurse handoff data elements, 4 ICU
  patients (2 standard, 2 complex), 50 items mapped to LOINC, 91 automated tests; rebuilding
  from the PhysioNet files reproduces the case files exactly.
- Two views of the same data under the same patient card (safety facts in both): a tabbed
  EHR-style control that opens on a Summary tab, and NurseGlance, one screen with seven
  organ-system cards and a Tasks & meds column (care done in the last 12 hours, doses and
  turns due next).
- An AWARE-style study mode (seeded crossover, practice questions, pause, event log, SUS
  and NASA-TLX, CSV export), a researcher page, transparent rule-based flags, and a
  virtual-nurse mode with a 10-minute break prompt.

**Results so far.** No nurse has used the app in a study. Click and time results are
design-level estimates from scripted runs.

| Research question | Result |
| --- | --- |
| 1. Can standard FHIR supply what nurses need at handoff? | 57 of 58 elements (98%) have a FHIR source. The conversion lost coded text (ventilator mode arrives as "49") and diagnosis priority, and chart items carry no standard codes. |
| 2. How much work does each view take per question? | Scripted shortest paths, keystroke-level model, 1440×900 screen: NurseGlance 3.2 s with no clicks, scrolls or hovers; tabbed view 12.4 s with 1.4 clicks and 1.9 scrolls. |
| 3. Which usability problems remain? | A heuristic evaluation found 10 major problems in version 0.2 (5 in NurseGlance, 3 in the control's fidelity, 2 in the study screen). All were fixed in version 0.3; 6 minor ones remain. |

**Next: a crossover study with ICU and virtual nurses.** Forty nurses (20 bedside ICU, 20
virtual) each answer 8 questions in each view, on different patients, then rate both views
with the SUS and NASA-TLX. The primary outcome is time per question, analyzed with a
mixed-effects model; 34 nurses give 80% power for a moderate effect (d<sub>z</sub> = 0.5).
The study needs IRB approval and a faculty principal investigator; the protocol is written
for a lab that runs such studies.

**Why CHIP.** The project carries the AWARE crossover design from physicians to bedside and
virtual nurses, whose cognitive fatigue Dr. Saif Khairat's group has measured with eye
tracking (in 22 of 29 encounters, first signs 9.8 to 11.9 minutes in; Khairat et al. 2025b),
and it logs each case's position within a view because his group found that reviewing a
complex case first raises ICU providers' burden (Khairat et al. 2026). It also draws on
visual analytics and human-factors evaluation, areas of CHIP faculty such as Dr. David Gotz and Dr. Amy Cole.

<small>Lindroth HL et al. Appl Clin Inform 2022;13(5):1207-1213. · Khairat S et al. (a) JMIR Res Protoc
2025;14:e74247 (NCT05937646); (b) JMIR Hum Factors 2025;12:e67111; and J Am Med Inform Assoc 2026;33(4):881-889. ·
Data: MIMIC-IV Clinical Database Demo on FHIR v2.1.0, PhysioNet, ODbL.</small>
