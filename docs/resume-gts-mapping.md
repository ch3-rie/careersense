# Resume to Graduate Tracer Survey mapping

This is the mapping used when a resume is parsed during registration (`POST /api/auth/register`) and when an alumnus uploads another resume (`POST /api/alumni/resumes`). Both calls use `extract_resume_from_upload`, then `map_to_gts_fields`. Registration then applies `apply_verified_registry`. The survey questions, option values, and submission contract are unchanged.

A blank extracted value stays blank. The parser does not invent a month, a salary band, an awarding body, or a Yes/No answer from missing text. The registration form still applies its existing defaults after prefill, including country `Philippines` and further studies `No` when the parser leaves that answer empty.

## Authority

| Destination | Source | Rule |
| --- | --- | --- |
| `degree`, `year_graduated` | Matched AUF registry record | When a registry row matches, those two fields replace the resume values. The resume value is kept only in `registry_overrides`. |
| `degree`, `year_graduated` | Earliest dated bachelor's degree in the education section | Used only when no registry row matches. A later bachelor's degree, master's degree, doctorate, diploma, or certificate is not the bachelor's degree. |
| `enroll_further_studies`, `further_studies` | Later education records | `Yes` and one program row only when a qualifying later program is present. Otherwise the parser leaves the answer empty. The form then shows the existing default, `No`. |
| `pres_occ`, `pres_emp` | Current job | When `present_job_is_first` is `Yes`, these are copied from the first job after graduation. |

## Personal information and bachelor's degree

| Destination | Source | Transformation |
| --- | --- | --- |
| `first_name`, `middle_name`, `last_name` | Name line in the resume | Split with particles, initials, and suffixes. A heading, title, or contact line is not a name. An uncertain part stays empty. |
| `country` | Contact or address text | Only a recognized country. Email and phone are read for validation and are not GTS fields. |
| `degree` | Primary bachelor's program | Earliest dated bachelor's degree. Registry wins when matched. |
| `year_graduated` | End year of that bachelor's degree | A lone year in an education block is not treated as graduation. Registry wins when matched. |

## Employment

Jobs stay separate records. The first job after graduation is the earliest role that was held on or after June of `year_graduated`. An internship dated before that cutoff stays in `experiences` and is not `first_occ`. A missing end date is not treated as current. `Present` or `Current` is required. If several jobs are current, the one with the latest start is the present job.

| Destination | Source | Transformation |
| --- | --- | --- |
| `ever_employed` | Jobs dated against graduation | `Yes` when a job is on or after graduation. `No` only when every job is dated before graduation. Otherwise empty. |
| `is_currently_employed` | Explicit current marker on a job | `Yes` or `No` only from that marker. Empty when current status is unknown. |
| `present_job_is_first` | First post-graduation job compared with the present job | `Yes` when they are the same role. |
| `first_occ`, `first_emp`, `first_sal`, `first_stat` | First job after graduation | Salary must match an official salary option. Hourly pay and an expected salary are not a current band. A title with no employer and no date is kept as a partial employment record and is not treated as the first job or as current employment. |
| `pres_occ`, `pres_emp`, `pres_head`, `pres_head_email`, `pres_stay` | Present job | Length of stay is calculated from a month-level start. A year-only start is not given an invented month here. |
| `time_to_first_job`, `after_grad_employment_duration` | Graduation year and first-job start | June of the graduation year is the survey assumption. A year-only start is placed in July only for this bucket, and `derivation.time_to_first_job_basis` is `estimated`. A month-level start is `confirmed`. Missing dates leave the bucket empty. |
| `first_related`, `present_related_degree` | Course-alignment result for the occupation | Existing alignment labels only. Unknown alignment does not become `No`. |

## Credentials, skills, and profile copy

| Destination | Source | Transformation |
| --- | --- | --- |
| `certifications` | Certification or license section | Name, awarding body, and year. A following organization or year stays on that record. No month is added to a year. |
| `seminars` | Seminar, training, or workshop section | Name, location, organizer, and year. Location maps to the seminar location field. |
| `awards` | Award or honor section | Title, issuer, year, and description. The note maps to description. |
| `skills` | Skills section | Declared skills only. Words inside job duties stay in `inferred_skills` and are not submitted as skills. |

On the alumni profile, `seed_resume_activity` copies certifications, seminars, and awards only into a section that has no rows yet. A section the graduate already filled is not replaced. A survey answer of `no` for that section copies nothing. A later call does not insert duplicates.

## Failure

If the file cannot be read, or the extracted text is not usable, the parser returns an empty result and a source of `failed` or `empty`. Registration still returns a draft, and the graduate completes the survey by hand. Resume text is untrusted data and is not allowed to change parser instructions.
