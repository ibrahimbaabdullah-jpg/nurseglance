# Data license and attribution

NurseGlance's code is MIT-licensed (see `LICENSE`). The data is not.

Files derived from MIMIC (`data/processed/*.json`, `docs/case_candidates.csv`,
`docs/cases_draft.md`, `docs/coverage.csv`, `etl/cases.json`) come from two
openly licensed PhysioNet datasets and are shared under the same license:
the **Open Data Commons Open Database License (ODbL) v1.0**
(https://opendatacommons.org/licenses/odbl/1-0/). If you share a modified
version of these files, share it under the ODbL too.

The data is de-identified, and dates are shifted into the future. It contains
no real patient's identity, and nothing here is for clinical use.

## Sources

Citations as each dataset's PhysioNet page gives them (checked 2026-11-27):

- **MIMIC-IV Clinical Database Demo on FHIR, v2.1.0.**
  Bennett, A., Ulrich, H., Wiedekopf, J., Szul, P., Grimes, J., & Johnson, A. (2025).
  MIMIC-IV Clinical Database Demo on FHIR (version 2.1.0). PhysioNet. RRID:SCR_007345.
  https://physionet.org/content/mimic-iv-fhir-demo/2.1.0/
- **MIMIC-IV Clinical Database Demo, v2.2 (CSV).**
  Johnson, A., Bulgarelli, L., Pollard, T., Horng, S., Celi, L. A., & Mark, R. (2023).
  MIMIC-IV Clinical Database Demo (version 2.2). PhysioNet. RRID:SCR_007345.
  https://doi.org/10.13026/dp1f-ex47
- The FHIR demo's original publication: Bennett AM, Ulrich H, van Damme P, Wiedekopf J,
  Johnson AE. MIMIC-IV on FHIR: converting a decade of in-patient data into an
  exchangeable, interoperable format. *J Am Med Inform Assoc.* 2023;30(4):718-725.
  https://doi.org/10.1093/jamia/ocad002
- PhysioNet's standard citation: Pollard, T., Moody, B. E., Lehman, L., Gow, B.,
  Fernandes, C., Xie, C., Johnson, A., Mark, R. G., & Heldt, T. (2026). PhysioNet as a
  global platform for biomedical research. *Nature Health.*
  https://doi.org/10.1038/s44360-026-00096-z
