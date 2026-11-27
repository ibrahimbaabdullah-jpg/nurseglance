# Proposed evaluation: a crossover usability study of NurseGlance with ICU and virtual nurses

**Status: proposed protocol, draft for review.** No nurse has been recruited and no study
data have been collected. The study is human-subjects research: it needs IRB approval and
a faculty principal investigator before anyone is contacted. It follows the design of the
AWARE crossover trial (Khairat et al. 2025, NCT05937646) and is written to be run in a lab
that already runs such studies.

## 1. Question and hypotheses

Compared with a tabbed, EHR-style view of the same FHIR data, does NurseGlance help ICU
nurses answer standard handoff questions faster, at least as accurately, and with less
workload?

- **H1 (primary):** time per question is shorter with NurseGlance.
- **H2:** accuracy is at least as high with NurseGlance.
- **H3:** NurseGlance needs fewer clicks and screens, gets a higher SUS score and a lower
  NASA-TLX score.
- **Exploratory:** whether the difference changes with case complexity (standard or
  complex) or role (bedside ICU nurse or virtual nurse), and what eye tracking shows about
  search and fatigue.

The design-level task analysis (`docs/task_analysis.md`) estimates 3.2 s per question for
NurseGlance and 12.4 s for the tabbed view, for an expert who knows where every value is.
It leaves out search, reading and judgment. Only a study with nurses can show whether the
difference holds.

## 2. Design

A randomized, counterbalanced, two-period crossover in one simulated session. Each nurse
uses both views. Each view gets one standard and one complex case, so each nurse sees each
of the 4 patients once and never sees the same patient in both views. Seeing new patients
in the second period is the washout.

**Randomization.** There are 8 sequences: which view comes first, which standard case goes
with NurseGlance, and which complex case goes with NurseGlance. Allocation is stratified by
role, with one list per role (`analysis/allocation.py`, one master seed each). Each list
holds all 8 sequences in every block of 8, and each half-block of 4 is balanced on all
three factors, so each role's 20 nurses include 10 who start with each view, and the 40
nurses give each sequence 5 times. Someone outside the session team makes the lists with
private master seeds. Each row gives the seed that the facilitator types into the app's
study mode, which rebuilds that nurse's plan and logs the seed. Case order within each view
(standard or complex first) stays random; it is logged and enters the analysis as each
case's position within its view, because reviewing a complex case first increased ICU
providers' eye fixations and task times (Khairat et al. 2026). Rule-based flags are off in
study mode, so the comparison tests the layout only.

## 3. Participants and setting

- **Bedside ICU nurses (target 20):** registered nurses with at least 6 months of adult
  ICU work in the past 3 years.
- **Virtual nurses (target 20):** registered nurses now working in an inpatient virtual
  nursing or tele-ICU program, with ICU experience. Virtual nurses review the chart at
  admission and discharge; in 75% (22 of 29) of the encounters that Khairat and colleagues
  recorded with eye tracking, the first instance of cognitive fatigue came 9.8 minutes into
  discharges and 11.9 minutes into admissions (Khairat et al. 2025, JMIR Hum Factors).
- **Exclusions:** anyone who helped design NurseGlance or wrote the questions.
- **Recruitment:** through nursing councils and professional email lists, not through
  nurses' managers. Taking part, or not, is never reported to an employer.
- **Setting:** a usability lab with a 1920×1080 monitor. In study mode, NurseGlance's
  patient card, seven organ-system cards and Tasks & meds column fit on one screen for all
  4 cases at 1920×1080 and at 1440×900. Remote sessions by video call are allowed on
  screens of at least 1440×900, and the screen size is recorded. Eye tracking is in the
  lab only.
- **Compensation:** a modest payment set by the lab's budget.

## 4. Materials

- **Cases and questions:** 4 ICU stays from the MIMIC-IV demo on FHIR (2 standard, 2
  complex) and 16 questions, 4 per case: a lookup, a trend, a timing and a synthesis
  question (`docs/case_questions.md`). Before the study, 2 ICU nurses outside the study
  team review the questions, answer keys and rubric, and the questions are revised.
- **Practice case:** a fifth demo stay (stay 35024147, a 32-year-old woman in the
  MICU/SICU with diabetic ketoacidosis) with 2 practice questions per view
  (`docs/practice_questions.json`). Practice answers are logged but never scored or
  analyzed. The 2 reviewing nurses check these questions too.
- **Software:** the app's study mode. It shows the question beside the view with a
  progress bar, logs every click and screen with a timestamp, runs the practice questions
  and the break, gives the SUS and raw NASA-TLX after each view, takes the facilitator's
  debrief notes, and exports CSV files. A Pause button hides the view and stops the
  clock for interruptions; paused time is logged and left out of the question's time.
  "End early" stops a session but keeps what was logged, for export and analysis.
  Scrolls are not logged yet; a scroll logger or a screen recording will be added before
  the pilot. The NASA-TLX sliders start at the midpoint (50), so the facilitator asks the
  nurse to set every slider, including any left at 50.

## 5. Procedure (about 60 minutes)

1. Electronic consent, then a short form: role, years of ICU experience, EHR used at work,
   age band and self-rated computer skill (5 min).
2. Training on the first view with the practice case (5 min).
3. Eight questions on the first view, 2 patients with 4 questions each (about 15 min). The
   nurse types each answer or presses "I can't find it". After 3 minutes on one question,
   the facilitator asks for a best answer or "I can't find it".
4. SUS and NASA-TLX for the first view (3 min), then a 2-minute break.
5. Training, eight questions and the two surveys on the second view (about 23 min).
6. A short debrief: which view they would use at handoff and why, and anything missing or
   misleading (about 10 min). Audio is recorded only with separate consent.

The virtual-nurse mode's 10-minute break prompt stays off, because it would interrupt the
timed questions.

## 6. Outcomes

| Outcome | Measure | Unit |
| --- | --- | --- |
| **Time (primary)** | Seconds from question shown to answer submitted, from the app log | Question |
| Accuracy | Lookup, trend and timing answers scored against the key; "I can't find it" counts as wrong; a question left unanswered because the session ended early is missing | Question |
| Synthesis quality | Rubric score 0 to 2, from two nurse raters who do not know which view was used; disagreements settled by discussion; weighted kappa reported | Question |
| Interactions | Clicks and screens, from the app log; scrolls once logged | Question |
| Usability | System Usability Scale, 0 to 100 (Brooke 1996) | View |
| Workload | Raw NASA-TLX, 0 to 100 (Hart 2006) | View |
| Eye tracking (exploratory, lab only) | Fixations per question, time to first fixation on the answer, pupil-based fatigue instances as in Khairat et al. 2020 (JAMA Netw Open) and 2025 (JMIR Hum Factors) | Question |
| Preference (exploratory) | Debrief answers | Nurse |

## 7. Sample size

The main comparison is within each nurse. For a paired comparison of each nurse's mean
log time under the two views, with a two-sided α of 0.05 and 80% power, a standardized
within-nurse effect of d<sub>z</sub> = 0.5 needs **34 nurses** (`analysis/sample_size.py`,
noncentral t; it agrees with G*Power). The target is **40 nurses**, to allow about 15% for
withdrawals and unusable sessions. With 40 completers, the smallest effect with 80% power
is d<sub>z</sub> = 0.454.

| d<sub>z</sub> | 0.4 | 0.5 | 0.6 | 0.8 |
| --- | --- | --- | --- | --- |
| Nurses for 80% power | 52 | 34 | 24 | 15 |
| Nurses for 90% power | 68 | 44 | 32 | 19 |

**Why a moderate effect.** In a randomized crossover study of an ICU interface of this kind,
with 20 critical care physicians, median task times were 54 to 93 s with the new interface
and 112 to 145 s with the standard EHR, a large difference (Ahmed et al. 2011). This study plans for a smaller one for three
reasons. Its control already shows the newest values first and running infusions at the
top, unlike an older EHR. The task-analysis estimates leave out search time, which likely
favors NurseGlance. And typing the answer adds the same time in both views. The paired calculation is an
approximation of the planned analysis: the mixed model uses all 16 answers per nurse, which
lowers within-nurse noise, but it also treats the 16 questions as a random sample, which
adds uncertainty. After the pilot, power for the mixed model will be checked by simulation
with the pilot's variance estimates (simr; Green and MacLeod 2016), and the target revised
if needed before the main sessions. The study is not powered to compare roles (20 per
group) or to test accuracy, where most lookups are expected to be correct in both views.

## 8. Analysis

- **Pre-registration:** hypotheses, outcomes and models are registered (OSF or
  ClinicalTrials.gov) before the first session.
- **Primary model:** a linear mixed-effects model of log time, with view, period, case
  type, case position within the view (first or second), question type and view × case
  type as fixed effects; a random intercept and view slope for each nurse; and a random
  intercept for each question. The result is the ratio of geometric mean times
  (NurseGlance to tabbed) with a 95% confidence interval, using Kenward-Roger degrees of
  freedom (lme4 and lmerTest in R; Bates et al. 2015; Kuznetsova et al. 2017).
- **Carryover:** different patients in each period prevent carryover of patient knowledge.
  The view × period interaction is reported but not used to choose the model (Senn 2002).
- **Accuracy:** a logistic mixed model with the same fixed effects and random intercepts
  for nurse and question. Synthesis scores use a cumulative-link mixed model.
- **Clicks and screens:** Poisson or negative binomial mixed models.
- **SUS and NASA-TLX:** linear mixed models with view and period, and a random intercept
  for each nurse.
- **Multiple outcomes:** one primary outcome; secondary outcomes use the Holm correction.
- **Missing data and sensitivity:** "I can't find it" answers stay in the primary analysis,
  timed until the button press. Sensitivity analyses drop them, and keep only correct
  answers. A nurse who finishes one period stays in the mixed model (study mode keeps the
  data of a session ended early); a sensitivity analysis drops such nurses.
- **Exploratory:** role × view and complexity × view interactions; whether starting a view
  with the complex case changes time or accuracy (Khairat et al. 2026); eye-tracking
  measures; debrief notes coded by two coders for themes.

## 9. Ethics, consent and data security

- **Review:** the protocol goes to the university IRB before any recruitment. The study
  is expected to be minimal risk; the IRB decides its review category.
- **No patient data:** the cases come from the de-identified MIMIC-IV demo, which is open
  to anyone under the ODbL license. No real patient's record is shown.
- **Consent:** electronic, key information first. Taking part is voluntary, a nurse can
  stop at any time, and no individual's performance is shared with any employer.
- **Identifiers:** the app stores only a run ID, never a name. The key that links a consent
  form to a run ID is kept apart from the study data on university-approved secure storage
  and destroyed after analysis. Screen recordings show only the app, and no face video is
  recorded. Audio is transcribed, de-identified and deleted.
- **Data sharing:** event logs and surveys stay encrypted on university storage. Only
  de-identified summary tables and the analysis code are shared publicly.
- **Conflict of interest:** the person who designed NurseGlance does not run sessions or
  score synthesis answers. A nurse informatician does both, as in the AWARE trial.

## 10. Limitations

- The tasks are simulated, on 4 patients from one hospital's demo data, with shifted dates
  and no free-text nursing notes.
- The control is a research build of a tabbed view, not the nurses' own EHR. AWARE used
  each site's own EHR as the control; a later study could do the same.
- The applicant wrote the questions and answer keys, so they need clinical review first.
  In the current draft all three Rising/Falling/Stable trend keys are "Falling"; the
  reviewers should change one so that always answering "Falling" cannot score 3 of 3.
- Nurses can tell which view is new, so they are not blinded. Synthesis scoring is.
- One session measures first use only. It says nothing about learning over time, real
  handoffs or patient outcomes.

## 11. Timeline, if a lab runs it

Months 1 and 2: question and practice-question review, scroll logging and IRB submission. Month
3: a pilot with 3 nurses under the approved protocol. Months 4 to 6: sessions. Months 7
and 8: analysis and write-up.

## References

- Ahmed A, Chandra S, Herasevich V, Gajic O, Pickering BW. The effect of two different
  electronic health record user interfaces on intensive care provider task load, errors of
  cognition, and performance. Crit Care Med. 2011;39(7):1626-1634.
  doi:10.1097/CCM.0b013e31821858a0
- Bates D, Mächler M, Bolker B, Walker S. Fitting linear mixed-effects models using lme4.
  J Stat Softw. 2015;67(1):1-48. doi:10.18637/jss.v067.i01
- Brooke J. SUS: a "quick and dirty" usability scale. In: Jordan PW, Thomas B, Weerdmeester
  BA, McClelland IL, eds. Usability Evaluation in Industry. Taylor & Francis; 1996:189-194.
- Green P, MacLeod CJ. SIMR: an R package for power analysis of generalized linear mixed
  models by simulation. Methods Ecol Evol. 2016;7(4):493-498. doi:10.1111/2041-210X.12504
- Hart SG. NASA-Task Load Index (NASA-TLX); 20 years later. Proc Hum Factors Ergon Soc
  Annu Meet. 2006;50(9):904-908. doi:10.1177/154193120605000909
- Khairat S, Coleman C, Ottmar P, Jayachander DI, Bice T, Carson SS. Association of
  electronic health record use with physician fatigue and efficiency. JAMA Netw Open.
  2020;3(6):e207385. doi:10.1001/jamanetworkopen.2020.7385
- Khairat S, Morelli J, Boynton MH, Bice T, Gold JA, Carson SS. Investigating information
  visualization to combat information overload in electronic health records: protocol for
  a randomized controlled trial. JMIR Res Protoc. 2025;14:e74247. doi:10.2196/74247
- Khairat S, Morelli J, Liao WT, Aucoin J, Edson BS, Jones CB. Association of virtual
  nurses' workflow and cognitive fatigue during inpatient encounters: cross-sectional
  study. JMIR Hum Factors. 2025;12:e67111. doi:10.2196/67111
- Khairat S, Morelli J, Yang S, Li Y, Herasevich V, Mohan D, Handzel R, Ratwani RM, Apathy
  NC, Boynton MH, Carson SS. Association of patient complexity with information processing
  and usability of electronic health records among ICU providers: a multicenter study.
  J Am Med Inform Assoc. 2026;33(4):881-889. doi:10.1093/jamia/ocag017
- Kuznetsova A, Brockhoff PB, Christensen RHB. lmerTest package: tests in linear mixed
  effects models. J Stat Softw. 2017;82(13):1-26. doi:10.18637/jss.v082.i13
- Lindroth HL, Pinevich Y, Barwise AK, et al. Information and data visualization needs
  among direct care nurses in the intensive care unit. Appl Clin Inform.
  2022;13(5):1207-1213. doi:10.1055/s-0042-1758735
- Senn S. Cross-over Trials in Clinical Research. 2nd ed. Wiley; 2002.
