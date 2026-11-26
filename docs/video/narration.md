# Demo video: narration script

The video (`nurseglance_demo.mp4`, 3 min 4 s, 1440×900) is recorded from the running app by `tools/record_demo.py`. Its captions are drawn into the picture, so it works without sound, and `nurseglance_demo.srt` holds the same captions as subtitles.

To add a voice-over, read each line when its caption appears. Each caption stays up long enough to read aloud at about 145 words a minute. After any change to the app, record again with `python tools/record_demo.py --out docs/video/nurseglance_demo.mp4` (app running on port 8501).

| Start | End | Narration |
| --- | --- | --- |
| 0:00 | 0:07 | NurseGlance: a nurse-centered ICU handoff dashboard built on HL7 FHIR data. Research prototype, not for clinical use. |
| 0:07 | 0:16 | The control: a tabbed EHR-style view of the same FHIR data, here for a ventilated patient on two vasopressors. |
| 0:16 | 0:22 | Vitals sit in flowsheet groups, one table per group, newest column first. |
| 0:22 | 0:29 | Labs are one long table: 94 results for this patient in the last 72 hours. |
| 0:29 | 0:38 | Drips and doses are under another tab, in sections. Answering one handoff question can mean several tabs and scrolls. |
| 0:38 | 0:44 | NurseGlance shows the same patient on one screen, organized by organ system. |
| 0:44 | 0:54 | At the top: every infusion running now with its rate, and the next dose of each drug in the 12 hours after handoff. |
| 0:54 | 1:06 | Each value shows the latest reading, a trend arrow, the 12-hour range and a sparkline. An H or L badge marks a value outside its threshold. |
| 1:06 | 1:12 | Drips show their rate, the last titration and when they started. |
| 1:12 | 1:21 | "None", "not charted" and "not in FHIR demo" stay separate, so a true negative is never mistaken for missing data. |
| 1:22 | 1:32 | Below the panels, a 12-hour timeline shows each dose and infusion after handoff. Pointing at a dose shows its name and time. |
| 1:32 | 1:43 | Optional rule-based flags. Each one shows its rule, the values, their times and FHIR ids. Thresholds are placeholders, and flags are off in study mode. |
| 1:43 | 1:49 | Study mode runs an AWARE-style crossover session, start to finish. |
| 1:49 | 1:55 | A logged seed sets the view order and which patients go with each view. |
| 1:55 | 2:03 | The question stays beside the view. Every click, screen and answer is logged with its time. |
| 2:03 | 2:10 | Here the answer is in the infusion strip: norepinephrine 0.2 mcg/kg/min. |
| 2:10 | 2:18 | After each view come the System Usability Scale and NASA-TLX, and the session exports CSV files for analysis. |
| 2:18 | 2:28 | Virtual-nurse mode: admission and discharge checklists, a session timer, and a break prompt at 10 minutes. |
| 2:28 | 2:37 | Virtual nurses showed cognitive fatigue within about 10 to 12 minutes of an encounter in a 2025 eye-tracking study. |
| 2:37 | 2:56 | So far: FHIR can supply 57 of 58 handoff elements. Scripted expert paths take 3.2 s per question in NurseGlance against 12.9 s in the tabbed view (design-level estimates, not nurse data). Next: a crossover study with ICU and virtual nurses, after IRB approval. |
| 2:56 | 3:02 | Code, reports and protocol: github.com/ibrahimbaabdullah-jpg/nurseglance. |

Research prototype, not for clinical use. Click and time figures in the video are design-level estimates from scripted runs, not measurements of nurses.
