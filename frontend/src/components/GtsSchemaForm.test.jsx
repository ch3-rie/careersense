import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import GtsSchemaForm from "./GtsSchemaForm";

function question(id, label, extra = {}) {
  return {
    id,
    field_key: extra.field_key ?? id,
    label,
    description: extra.description || "",
    type: extra.type || "short_answer",
    required: Boolean(extra.required),
    options: extra.options || [],
    placeholder: extra.placeholder || "",
    default_value: extra.default_value ?? (extra.type === "checkboxes" ? [] : ""),
    storage: "core",
    visibility: extra.visibility || null,
    validation: extra.validation || {},
    repeatable: extra.repeatable || null,
  };
}

function show(field, value, op = "eq") {
  return { logic: "and", rules: [{ field_id: field, op, value }] };
}

function showAll(rules) {
  return { logic: "and", rules };
}

const schema = {
  title: "Graduate Tracer Survey",
  sections: [
    {
      id: "general",
      key: "general",
      name: "General Information",
      description: "Your name, degree, and household background.",
      subsections: [{
        id: "general_main",
        name: "",
        questions: [
          question("first_name", "Given name", { required: true }),
          question("middle_name", "Middle name"),
          question("last_name", "Last name", { required: true }),
          question("country", "Country of residence", { default_value: "Philippines" }),
          question("year_graduated", "Year graduated", { required: true }),
          question("degree", "Bachelor's degree earned", { required: true }),
          question("extra_note", "Campus organization"),
        ],
      }],
    },
    {
      id: "employment",
      key: "employment",
      name: "Employment",
      description: "Your first job after graduation and your current work.",
      subsections: [
        {
          id: "first_job",
          name: "First job after graduation",
          description: "Your first job after you earned your bachelor's degree.",
          questions: [
            question("ever_employed", "Have you been employed after graduation?", { type: "yes_no", required: true }),
            question("first_occ", "Occupation (first job)", { required: true, visibility: show("ever_employed", "Yes") }),
            question("first_emp", "Employer (first job)", { required: true, visibility: show("ever_employed", "Yes") }),
            question("first_stat", "Employment status (first job)", {
              type: "multiple_choice",
              required: true,
              options: ["Regular/Permanent", "Self-Employed"],
              visibility: show("ever_employed", "Yes"),
            }),
            question("time_to_first_job", "After graduation, how long did it take you to be employed?", {
              type: "dropdown",
              options: ["Less than a month", "1 to 6 months"],
              visibility: show("ever_employed", "Yes"),
            }),
          ],
        },
        {
          id: "current_employment",
          name: "Current Employment",
          questions: [
            question("is_currently_employed", "Are you currently employed?", { type: "yes_no", required: true }),
            question("present_job_is_first", "Is your present job also your first job after college?", {
              type: "yes_no",
              visibility: show("is_currently_employed", "Yes"),
            }),
            question("pres_occ", "Occupation (present)", {
              visibility: showAll([
                { field_id: "is_currently_employed", op: "eq", value: "Yes" },
                { field_id: "present_job_is_first", op: "eq", value: "No" },
              ]),
            }),
            question("pres_emp", "Employer", {
              visibility: showAll([
                { field_id: "is_currently_employed", op: "eq", value: "Yes" },
                { field_id: "present_job_is_first", op: "eq", value: "No" },
              ]),
            }),
          ],
        },
        {
          id: "employment_details",
          name: "Employment Details",
          questions: [
            question("reason_current", "Reason/s (current unemployment)", {
              type: "checkboxes",
              options: ["Continuing Education", "Other"],
              visibility: show("is_currently_employed", "No"),
            }),
          ],
        },
      ],
    },
    {
      id: "studies",
      key: "studies",
      name: "Further Education and Professional Development",
      description: "Additional education, certifications, seminars, and awards.",
      subsections: [{
        id: "studies_main",
        name: "",
        questions: [
          question("enroll_further_studies", "Did you enroll in further studies after graduation?", {
            type: "yes_no",
            default_value: "No",
          }),
          question("further_studies", "Study programs", {
            type: "repeatable_group",
            default_value: [],
            visibility: show("enroll_further_studies", "Yes"),
            repeatable: {
              fields: [
                { id: "school", label: "Institution", required: true },
                { id: "course_degree", label: "Program", required: true },
              ],
            },
          }),
        ],
      }],
    },
    {
      id: "feedback",
      key: "feedback",
      name: "Institutional Feedback",
      description: "Seminars, engagement, and suggestions for AUF.",
      subsections: [{
        id: "feedback_main",
        name: "",
        questions: [
          question("participated_seminars", "Did you participate in AUF career development seminars?", { type: "yes_no" }),
          question("seminars_helpful", "Were these seminars helpful in your employment experience?", {
            type: "yes_no",
            visibility: show("participated_seminars", "Yes"),
          }),
          question("mentoring_rating", "Mentoring others", {
            type: "scale",
            description: "How much has AUF inspired you to do each of the following?",
            options: [
              { value: "3", label: "3 · Great extent" },
              { value: "2", label: "2 · Small extent" },
              { value: "1", label: "1 · Not at all" },
            ],
          }),
          question("engagement_desc", "Description of your engagements and their impact", { type: "paragraph" }),
          question("curriculum_suggestions.include_new_courses", "Include new courses/subjects", {
            field_key: "curriculum_suggestions.include_new_courses",
            description: "Suggestions for improving the curriculum.",
          }),
        ],
      }],
    },
  ],
};

function renderForm(props = {}) {
  const onSubmit = props.onSubmit || vi.fn();
  const view = render(
    <GtsSchemaForm
      schema={schema}
      variant="review"
      confirmSubmit
      submitLabel="Submit tracer information"
      onSubmit={onSubmit}
      {...props}
    />
  );
  return { ...view, onSubmit, user: userEvent.setup() };
}

async function fillGeneral(user) {
  await user.type(screen.getByLabelText(/Given name/), "Ana");
  await user.type(screen.getByLabelText(/Last name/), "Santos");
  await user.clear(screen.getByLabelText(/Year graduated/));
  await user.type(screen.getByLabelText(/Year graduated/), "2024");
  await user.type(screen.getByLabelText(/^Bachelor's degree earned/), "BS Accountancy");
}

async function openEmployment(user) {
  await user.click(screen.getByRole("tab", { name: /Employment/ }));
}

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

describe("Graduate Tracer Survey form", () => {
  test("shows section progress and moves between sections from the tabs and footer", async () => {
    const { user } = renderForm();
    expect(screen.getByText("Section 1 of 4 — General Information")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    expect(screen.getByRole("tab", { name: /General Information, Not completed, current section/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByLabelText("Campus organization")).toBeInTheDocument();

    screen.getByRole("tab", { name: /General Information/ }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("heading", { name: "First job after graduation" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Employment, Not completed, current section/ })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("heading", { name: "Further studies" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Previous" }));
    expect(screen.getByRole("heading", { name: "Current Employment" })).toBeInTheDocument();
  });

  test("uses radios and checkboxes, and reveals only the employment questions that apply", async () => {
    const { user } = renderForm();
    await openEmployment(user);
    expect(screen.queryByLabelText(/Occupation \(first job\)/)).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Continuing Education" })).not.toBeInTheDocument();

    const ever = screen.getByRole("group", { name: /Have you been employed after graduation/ });
    const yes = within(ever).getByRole("radio", { name: "Yes" });
    yes.focus();
    await user.keyboard(" ");
    expect(yes).toBeChecked();
    expect(screen.getByLabelText(/Occupation \(first job\)/)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /how long did it take/ })).toHaveDisplayValue("Select");

    const current = screen.getByRole("group", { name: /Are you currently employed/ });
    await user.click(within(current).getByRole("radio", { name: "No" }));
    expect(screen.queryByLabelText("Occupation (present)")).not.toBeInTheDocument();
    const reasons = screen.getByRole("group", { name: /Reason\/s \(current unemployment\)/ });
    const education = within(reasons).getByRole("checkbox", { name: "Continuing Education" });
    const other = within(reasons).getByRole("checkbox", { name: "Other" });
    await user.click(education);
    await user.click(other);
    expect(education).toBeChecked();
    expect(other).toBeChecked();
    await user.click(education);
    expect(education).not.toBeChecked();
    expect(other).toBeChecked();
  });

  test("keeps answers when a conditional section is hidden and confirms before removing a filled entry", async () => {
    const { user } = renderForm({
      resume: {
        parser_source: "llm",
        further_studies: [{ school: "AUF", course_degree: "MBA" }],
      },
    });
    await user.click(screen.getByRole("tab", { name: /Further Education/ }));
    const enroll = screen.getByRole("group", { name: /Did you enroll in further studies/ });
    await user.click(within(enroll).getByRole("radio", { name: "Yes" }));
    await user.click(screen.getByRole("button", { name: "Add another program" }));
    await user.type(screen.getByPlaceholderText("School or university"), "AUF");
    await user.type(screen.getByPlaceholderText("Program or degree"), "MBA");
    expect(screen.getByText("Suggested from your resume")).toBeInTheDocument();

    await user.click(within(enroll).getByRole("radio", { name: "No" }));
    expect(screen.queryByPlaceholderText("School or university")).not.toBeInTheDocument();
    await user.click(within(enroll).getByRole("radio", { name: "Yes" }));
    expect(screen.getByPlaceholderText("School or university")).toHaveValue("AUF");
    expect(screen.getByPlaceholderText("Program or degree")).toHaveValue("MBA");

    await user.click(screen.getByRole("button", { name: "Remove program 1" }));
    expect(screen.getByRole("alertdialog", { name: "Remove this program?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByPlaceholderText("School or university")).toHaveValue("AUF");

    await user.click(screen.getByRole("button", { name: "Edit in General Information" }));
    expect(screen.getByLabelText(/Given name/)).toBeInTheDocument();
  });

  test("shows a resume comparison only when extraction succeeded and the field is valid", async () => {
    const { user } = renderForm({
      initial: { degree: "BS Accountancy", year_graduated: "2020" },
      resume: { parser_source: "llm", degree: "BS Nursing", year_graduated: "2020" },
    });
    expect(screen.getByText(/Your resume lists BS Nursing as your bachelor's degree/)).toBeInTheDocument();

    cleanup();
    renderForm({
      initial: { degree: "BS Accountancy" },
      resume: { parser_source: "failed", degree: "BS Nursing" },
    });
    expect(screen.queryByText(/Your resume lists BS Nursing/)).not.toBeInTheDocument();

    cleanup();
    const strict = structuredClone(schema);
    strict.sections[0].subsections[0].questions.find((item) => item.id === "degree").validation = { max_length: 4 };
    renderForm({
      schema: strict,
      initial: { degree: "Accountancy", year_graduated: "2020" },
      resume: { parser_source: "llm", degree: "Nursing", year_graduated: "2020" },
    });
    expect(screen.getByText(/Your resume lists Nursing as your bachelor's degree/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Submit tracer information" }));
    expect(screen.getByText("Please keep this under 4 characters.")).toBeInTheDocument();
    expect(screen.queryByText(/Your resume lists Nursing/)).not.toBeInTheDocument();
  });

  test("validates visible required answers, opens the first invalid section, and ignores hidden fields", async () => {
    const { user } = renderForm();
    await user.click(screen.getByRole("button", { name: "Submit tracer information" }));
    expect(screen.getByText("Please answer: Given name")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /General Information/ })).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByText("Enter your current occupation.")).not.toBeInTheDocument();

    await fillGeneral(user);
    await openEmployment(user);
    const ever = screen.getByRole("group", { name: /Have you been employed after graduation/ });
    await user.click(within(ever).getByRole("radio", { name: "No" }));
    await user.click(screen.getByRole("button", { name: "Submit tracer information" }));
    expect(screen.getByText("Please answer: Are you currently employed?")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Occupation \(first job\)/)).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Employment/ })).toHaveAttribute("aria-invalid", "true");
  });

  test("submits once from the confirmation panel and keeps the request from being repeated", async () => {
    let release = () => {};
    const onSubmit = vi.fn(() => new Promise((resolve) => {
      release = resolve;
    }));
    const { user } = renderForm({ onSubmit });
    await fillGeneral(user);
    await openEmployment(user);
    const ever = screen.getByRole("group", { name: /Have you been employed after graduation/ });
    await user.click(within(ever).getByRole("radio", { name: "Yes" }));
    await user.type(screen.getByLabelText(/Occupation \(first job\)/), "Auditor");
    await user.type(screen.getByLabelText(/Employer \(first job\)/), "AUF");
    await user.click(screen.getByRole("radio", { name: "Regular/Permanent" }));
    const current = screen.getByRole("group", { name: /Are you currently employed/ });
    await user.click(within(current).getByRole("radio", { name: "Yes" }));
    const sameJob = screen.getByRole("group", { name: /present job also your first job/ });
    await user.click(within(sameJob).getByRole("radio", { name: "Yes" }));

    await user.click(screen.getByRole("button", { name: "Submit tracer information" }));
    expect(screen.getByRole("heading", { name: "Ready to submit?" })).toBeInTheDocument();
    expect(screen.getByText(/official tracer record/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    const confirm = screen.getByRole("button", { name: "Submit tracer information" });
    await user.click(confirm);
    await user.click(confirm);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0].current_occupation).toBe("Auditor");
    expect(onSubmit.mock.calls[0][0].current_employer).toBe("AUF");
    expect(screen.getByRole("button", { name: "Submitting…" })).toBeDisabled();
    release();
  });

  test("shows seminar follow-up questions and optional engagement choices", async () => {
    const { user } = renderForm();
    await user.click(screen.getByRole("tab", { name: /Institutional Feedback/ }));
    expect(screen.queryByRole("group", { name: /Were these seminars helpful/ })).not.toBeInTheDocument();
    const joined = screen.getByRole("group", { name: /AUF career development seminars/ });
    await user.click(within(joined).getByRole("radio", { name: "Yes" }));
    expect(screen.getByRole("group", { name: /Were these seminars helpful/ })).toBeInTheDocument();
    const scale = screen.getByRole("group", { name: /Mentoring others/ });
    const choice = within(scale).getByRole("radio", { name: "3 · Great extent" });
    expect(choice).not.toBeChecked();
    await user.click(choice);
    expect(choice).toBeChecked();
    expect(screen.getByLabelText(/Description of your engagements/)).toBeInTheDocument();
    expect(screen.getByLabelText("Include new courses/subjects")).toBeInTheDocument();
  });
});
