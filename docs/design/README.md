# Design mockup (version 1.2)

Version 1.2 takes its look from a static design mockup of the Handoff and
Virtual-nurse screens. These two screenshots of the mockup are kept for reference:

- `mockup_handoff.png`: Glance view, Handoff mode, at 1440×900.
- `mockup_virtual_nurse.png`: Glance view, Virtual-nurse mode, with the session band.

The mockup holds made-up demo values ("Demo patient B"). The app fills the same
layout with the MIMIC-IV demo cases and changes it where the data or the study
need it:

- **One screen per patient.** Rows are on one line instead of the mockup's two, so
  a whole complex patient still fits a 1440×900 screen in study mode and the task
  analysis keeps its zero-scroll result.
- **Only data that exists.** No "stable" or "improving" labels, which would be a
  clinical judgment; allergies read "Not in FHIR demo" because MIMIC-IV has no
  allergy table; code status reads "Not charted" unless a DNR diagnosis code exists.
- **Tasks & meds.** Due times are the eMAR doses given after handoff (the demo has no
  order schedule), and the 2-hour turn is a placeholder rule that says so.
- **No dead buttons.** Every control on screen works; there is no button for
  something the prototype does not do.

Colors and spacing are in `app/ui.py` (`CSS` tokens) and `.streamlit/config.toml`.
Inter and Space Grotesk are served from `static/fonts/` under the SIL Open Font License.
