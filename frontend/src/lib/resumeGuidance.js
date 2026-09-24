function text(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function clip(value, max = 80) {
  const raw = text(value);
  if (raw.length <= max) return raw;
  return `${raw.slice(0, max - 1).trim()}…`;
}

function yesNo(value) {
  const raw = text(value).toLowerCase();
  if (raw === "yes" || raw === "y" || raw === "true" || raw === "1") return "Yes";
  if (raw === "no" || raw === "n" || raw === "false" || raw === "0") return "No";
  return "";
}

function isCurrentJob(job) {
  return ["yes", "true"].includes(text(job?.is_current).toLowerCase());
}

function currentJob(experiences) {
  const rows = experiences.filter(isCurrentJob);
  return rows.length ? rows[rows.length - 1] : null;
}

function rolePhrase(job) {
  const title = clip(job?.job_title);
  const employer = clip(job?.employer, 60);
  if (title && employer) return `${title} at ${employer}`;
  return title || employer;
}

const SOFT = "Your resume contains information that may be relevant to this answer. Please review your response.";

function experiencesOf(resume) {
  return Array.isArray(resume.experiences) ? resume.experiences.filter((item) => item && typeof item === "object") : [];
}

function employmentNote(resume, choice) {
  const experiences = experiencesOf(resume);
  const current = currentJob(experiences);
  const confidence = text(resume.extraction_meta?.confidence?.current_employment).toLowerCase();
  const resumeSaysYes = yesNo(resume.is_currently_employed) === "Yes" && Boolean(text(current?.job_title));
  const resumeSaysNo = yesNo(resume.is_currently_employed) === "No" && !current;
  if (choice === "No" && resumeSaysYes) {
    if (confidence === "low") return SOFT;
    const phrase = rolePhrase(current);
    return phrase
      ? `Your resume appears to contain a recent employment record as ${phrase}. Please verify that your current employment status is correct.`
      : SOFT;
  }
  if (choice === "Yes" && resumeSaysNo && confidence === "high") {
    return "Your resume does not appear to list a current job. Please verify that you are currently employed.";
  }
  return "";
}

function everEmployedNote(resume, choice) {
  if (choice !== "No") return "";
  const job = experiencesOf(resume).find((item) => text(item.job_title) || text(item.employer));
  if (!job) return "";
  const phrase = rolePhrase(job);
  return phrase
    ? `Your resume appears to list work experience as ${phrase}. Please verify whether you have been employed after graduation.`
    : SOFT;
}

function studiesEvidence(resume) {
  const explicit = resume.further_studies_evidence;
  if (explicit && typeof explicit === "object" && explicit.status) return explicit;
  const studies = Array.isArray(resume.further_studies) ? resume.further_studies : [];
  const entries = studies
    .filter((item) => text(item?.course_degree) || text(item?.school))
    .map((item) => ({
      institution: text(item.school),
      program: text(item.course_degree),
      confidence: "high",
    }));
  return { status: entries.length ? "detected" : "not_detected", entries };
}

function studyPhrase(entry) {
  const program = clip(entry?.program);
  const school = clip(entry?.institution, 60);
  if (program && school) return `${program} at ${school}`;
  return program || school;
}

function studiesNote(resume, choice) {
  const evidence = studiesEvidence(resume);
  if (evidence.status === "unclear") {
    return "Your resume does not clearly show whether you have further studies. Please answer based on your own records.";
  }
  const phrases = (evidence.entries || []).map(studyPhrase).filter(Boolean).slice(0, 2);
  if (evidence.status === "detected") {
    const detail = phrases.length ? ` (${phrases.join("; ")})` : "";
    if (choice === "No") {
      return `Your resume appears to include further studies${detail}. Please review your answer before continuing.`;
    }
    if (choice === "Yes") {
      return phrases.length
        ? `Suggested from your resume: ${phrases.join("; ")}. Review this information and edit it if it is not correct. It is not saved until you submit.`
        : "Your resume appears to include further studies. Please review your answer and confirm whether this information is correct.";
    }
    return `Your resume appears to include further studies${detail}. Please review your answer and confirm whether this information is correct.`;
  }
  if (choice === "Yes" || choice === "No") {
    return "We did not find clear evidence of further studies in your resume. Please confirm whether you have completed or are currently pursuing further studies.";
  }
  return "";
}

function alignmentNote(related, choice, score, yesMessage, noMessage) {
  if (!related || choice === related) return "";
  if (!Number.isFinite(score) || score < 0.45) return SOFT;
  if (choice === "No" && related === "Yes") return yesMessage;
  if (choice === "Yes" && related === "No") return noMessage;
  return "";
}

function presentAlignmentNote(resume, choice) {
  const course = resume.course_alignment && typeof resume.course_alignment === "object" ? resume.course_alignment : {};
  return alignmentNote(
    yesNo(course.related_to_degree),
    choice,
    Number(course.confidence),
    "Based on the occupation and skills extracted from your resume, your current role may be related to your degree. Please review your answer before submitting.",
    "Your resume information may indicate that your current role is different from your degree field. Please verify your answer.",
  );
}

function firstAlignmentNote(resume, choice) {
  const related = yesNo(experiencesOf(resume)[0]?.related_to_degree);
  const low = text(resume.extraction_meta?.confidence?.job_title).toLowerCase() === "low";
  if (!related || choice === related) return "";
  if (low) return SOFT;
  return alignmentNote(
    related,
    choice,
    1,
    "The first job extracted from your resume may be related to your degree. Please review your answer before submitting.",
    "The first job extracted from your resume may be in a different field from your degree. Please verify your answer.",
  );
}

function sameJobNote(resume, choice) {
  const experiences = experiencesOf(resume);
  const first = experiences[0];
  const current = currentJob(experiences);
  if (!first || !current) return "";
  const firstTitle = text(first.job_title).toLowerCase();
  const currentTitle = text(current.job_title).toLowerCase();
  const firstEmployer = text(first.employer).toLowerCase();
  const currentEmployer = text(current.employer).toLowerCase();
  let suggestion = "";
  if (first !== current && firstTitle && currentTitle && firstTitle !== currentTitle) suggestion = "No";
  else if (first !== current && firstTitle && currentTitle && firstTitle === currentTitle && firstEmployer && currentEmployer && firstEmployer !== currentEmployer) suggestion = "No";
  else if (first === current || (firstTitle && currentTitle && firstTitle === currentTitle && (!firstEmployer || !currentEmployer || firstEmployer === currentEmployer))) suggestion = "Yes";
  if (!suggestion || choice === suggestion) return "";
  if (suggestion === "No") {
    const earlier = rolePhrase(first);
    const later = rolePhrase(current);
    if (earlier && later) {
      return `Your resume lists ${earlier} and ${later} as separate roles. Please verify whether your present job is also your first job.`;
    }
    return SOFT;
  }
  return "Your resume appears to describe one job after graduation. Please verify whether your present job is also your first job.";
}

export function resumeGuidance(questionId, answer, resume) {
  const choice = yesNo(answer);
  if (!choice || !resume || typeof resume !== "object") return "";
  const source = text(resume.parser_source).toLowerCase();
  if (source === "failed" || source === "empty") return "";
  if (questionId === "is_currently_employed") return employmentNote(resume, choice);
  if (questionId === "ever_employed") return everEmployedNote(resume, choice);
  if (questionId === "enroll_further_studies") return studiesNote(resume, choice);
  if (questionId === "present_related_degree") return presentAlignmentNote(resume, choice);
  if (questionId === "first_related") return firstAlignmentNote(resume, choice);
  if (questionId === "present_job_is_first") return sameJobNote(resume, choice);
  return "";
}
