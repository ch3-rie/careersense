-- CareerSense sample data for Render PostgreSQL (pgAdmin Query Tool).
-- Paste and run this whole script.
--
-- Removes previous sample alumni and their registry rows:
--   emails ending in .sample@example.com
--   student numbers starting with SAMP-
-- Administrator accounts are kept.
--
-- Inserts 100 alumni with registry, account, profile, jobs, skills,
-- further study, seminar, award, certification, resume, tracer survey,
-- alignment, alumni card, and notification filled in.
-- Student numbers use the registrar format YYYY-NNNN, for example 2016-8001.
-- Sample alumni password: Alumni@2026
-- Photo, cover, and certificate files are left blank because they are uploads.

BEGIN;

DO $seed$
DECLARE
  sample_password text := '$2b$12$lr2i8fYccLPIYvuOuHL0A.P27ZU54pYfRw0wiaw1F7YC5aPkg/Uoi';
  first_names text[] := ARRAY[
    'Andrea','Rafael','Camille','Dominic','Isabelle','Paolo','Hanna','Miguel','Sofia','Carlo',
    'Jasmine','Nathan','Bianca','Leo','Patricia','Gabriel','Elena','Marco','Chloe','Adrian',
    'Nina','Justin','Ethan','Mika','Rosa','Theo','Julia','Kyle','Lara','Mia'
  ];
  middle_names text[] := ARRAY[
    'Santos','Cruz','Reyes','Garcia','Lim','Diaz','Torres','Bautista','Pineda','Villanueva',
    'Aquino','Dela Cruz','Mendoza','Flores','Navarro','Ramos','Ong','Chua','Tan','Lopez'
  ];
  last_names text[] := ARRAY[
    'Bautista','Mendoza','Flores','Villanueva','Navarro','Santos','Cruz','Ramos','Garcia','Lopez',
    'Dela Cruz','Tan','Ong','Chua','Lim','Reyes','Aquino','Pineda','Torres','Bautista'
  ];
  cities text[] := ARRAY[
    'Angeles City','San Fernando','Mabalacat','Porac','Magalang','Mexico','Clark','Bacolor'
  ];
  find_jobs text[] := ARRAY[
    'Response to an advertisement','As walk-in applicant','Recommended by someone',
    'Information from friends','Family business','Arranged by AUF',
    'Public Employment Service Office / Job Fair'
  ];
  salaries text[] := ARRAY[
    'Below ₱13,800','₱13,800 to ₱27,599','₱27,600 to ₱41,399',
    '₱41,400 to ₱55,199','₱55,200 to ₱68,999','₱69,000 and above'
  ];
  job_stats text[] := ARRAY['Probationary','Regular/Permanent','Contractual/Casual','Self-Employed'];
  waits text[] := ARRAY[
    'Less than a month','1 to 6 months','7 to 11 months',
    '1 year to less than 2 years','2 years to less than 3 years','3 years or more'
  ];
  guardians text[] := ARRAY['Both Parents','Father','Mother','Other'];
  cards text[] := ARRAY[
    'Claimed','ReadyForPickup','Approved','ForVerification','ForRenewal','NotYetApplied','Processing'
  ];
  reason_codes text[] := ARRAY['seeking','further_studies','personal_family','health','not_seeking','other'];
  reason_labels text[] := ARRAY[
    'Looking for a job, but cannot find one','Continuing Education','Family-related reason/s',
    'Health-related reason/s','Not Currently Seeking Employment','Other'
  ];
BEGIN
  INSERT INTO soc_codes (soc_code, code, description, title_patterns, degree_patterns, category, major_group)
  SELECT * FROM (VALUES
    ('1330', '1330', 'Information and Communications Technology Service Managers', 'it manager,information technology manager', 'information technology,computer science', 'ICT', '1'),
    ('2512', '2512', 'Software Developers', 'software developer,software engineer,web developer,programmer', 'information technology,computer science,computer engineering', 'ICT', '2'),
    ('2511', '2511', 'Systems Analysts', 'systems analyst,it analyst', 'information technology,computer science', 'ICT', '2'),
    ('2522', '2522', 'Systems Administrators', 'systems administrator,it support specialist', 'information technology,computer science', 'ICT', '2'),
    ('3512', '3512', 'Information and Communications Technology User Support Technicians', 'it support,computer technician', 'information technology,computer science', 'ICT', '3'),
    ('2411', '2411', 'Accountants', 'accountant,auditor,bookkeeper', 'accountancy,accounting', 'Business and Administration', '2'),
    ('1211', '1211', 'Finance Managers', 'finance manager,accounting manager', 'accountancy,finance', 'Business and Administration', '1'),
    ('1221', '1221', 'Sales and Marketing Managers', 'sales manager,marketing manager', 'marketing,business administration', 'Sales and Marketing', '1'),
    ('2221', '2221', 'Nursing Professionals', 'staff nurse,registered nurse', 'nursing', 'Health', '2'),
    ('2341', '2341', 'Primary School Teachers', 'elementary teacher,primary school teacher', 'elementary education,education', 'Education', '2'),
    ('2330', '2330', 'Secondary Education Teachers', 'high school teacher,secondary teacher', 'secondary education,education', 'Education', '2'),
    ('2142', '2142', 'Civil Engineers', 'civil engineer,site engineer', 'civil engineering', 'Engineering', '2'),
    ('2152', '2152', 'Electronics Engineers', 'electronics engineer', 'electronics engineering', 'Engineering', '2'),
    ('2161', '2161', 'Building Architects', 'architect,junior architect', 'architecture', 'Engineering', '2'),
    ('1412', '1412', 'Restaurant Managers', 'restaurant manager,front office', 'hospitality management', 'Hospitality', '1'),
    ('2431', '2431', 'Advertising and Marketing Professionals', 'marketing specialist,content associate', 'communication,marketing', 'Sales and Marketing', '2'),
    ('2634', '2634', 'Psychologists', 'psychologist,guidance associate,hr assistant', 'psychology', 'Social Sciences', '2'),
    ('3212', '3212', 'Medical and Pathology Laboratory Technicians', 'medical technologist,laboratory aide', 'medical technology', 'Health', '3'),
    ('2262', '2262', 'Pharmacists', 'pharmacist,pharmacy assistant', 'pharmacy', 'Health', '2'),
    ('1120', '1120', 'Managing Directors and Chief Executives', 'store owner,managing director', 'business administration', 'Management', '1'),
    ('4110', '4110', 'General Office Clerks', 'office clerk,office staff,encoder', 'business administration,office administration', 'Clerical', '4'),
    ('3355', '3355', 'Police Officers', 'police officer', 'criminology', 'Public safety', '3')
  ) AS v(soc_code, code, description, title_patterns, degree_patterns, category, major_group)
  WHERE NOT EXISTS (
    SELECT 1 FROM soc_codes c WHERE c.soc_code = v.soc_code OR c.code = v.code
  );

  CREATE TEMP TABLE removed_accounts ON COMMIT DROP AS
  SELECT id, linked_student_id, personal_email
  FROM accounts
  WHERE role <> 'Admin'
    AND (
      personal_email LIKE '%.sample@example.com'
      OR COALESCE(linked_student_id, '') LIKE 'SAMP-%'
    );

  CREATE TEMP TABLE removed_students ON COMMIT DROP AS
  SELECT linked_student_id AS student_id
  FROM removed_accounts
  WHERE linked_student_id IS NOT NULL
  UNION
  SELECT student_id
  FROM university_records
  WHERE student_id LIKE 'SAMP-%'
     OR personal_email LIKE '%.sample@example.com';

  IF to_regclass('public.profile_reminder_sends') IS NOT NULL THEN
    DELETE FROM profile_reminder_sends
    WHERE alumni_id IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.profile_update_request_recipients') IS NOT NULL THEN
    DELETE FROM profile_update_request_recipients
    WHERE alumni_id IN (SELECT id FROM removed_accounts)
       OR request_id IN (
         SELECT id FROM profile_update_requests
         WHERE created_by IN (SELECT id FROM removed_accounts)
       );
  END IF;

  IF to_regclass('public.profile_update_requests') IS NOT NULL THEN
    DELETE FROM profile_update_requests
    WHERE created_by IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.email_outbox') IS NOT NULL THEN
    DELETE FROM email_outbox
    WHERE account_id IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.password_reset_verifications') IS NOT NULL THEN
    DELETE FROM password_reset_verifications
    WHERE account_id IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.partner_activities') IS NOT NULL THEN
    UPDATE partner_activities
    SET related_activity_id = NULL
    WHERE related_activity_id IN (
      SELECT id FROM partner_activities
      WHERE alumni_account_id IN (SELECT id FROM removed_accounts)
    );
    DELETE FROM partner_activities
    WHERE alumni_account_id IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.alumni_perk_redemptions') IS NOT NULL THEN
    DELETE FROM alumni_perk_redemptions
    WHERE account_id IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.alumni_badges') IS NOT NULL THEN
    DELETE FROM alumni_badges
    WHERE account_id IN (SELECT id FROM removed_accounts);
  END IF;

  DELETE FROM alumni_notifications WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM alumni_cards WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM alignment_results WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM alumni_skills WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM alumni_awards WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM alumni_seminars WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM alumni_certifications WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM further_studies WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM alumni_jobs WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM tracer_submissions WHERE account_id IN (SELECT id FROM removed_accounts)
     OR student_id IN (SELECT student_id FROM removed_students);
  DELETE FROM resumes WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM alumni_profiles WHERE account_id IN (SELECT id FROM removed_accounts);
  DELETE FROM admin_logs WHERE admin_id IN (SELECT id FROM removed_accounts);

  IF to_regclass('public.job_title_mappings') IS NOT NULL THEN
    UPDATE job_title_mappings
    SET last_modified_by = NULL
    WHERE last_modified_by IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.survey_definitions') IS NOT NULL THEN
    UPDATE survey_definitions
    SET published_by_id = NULL
    WHERE published_by_id IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.survey_versions') IS NOT NULL THEN
    UPDATE survey_versions
    SET published_by_id = NULL
    WHERE published_by_id IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.registry_imports') IS NOT NULL THEN
    UPDATE registry_imports
    SET admin_id = NULL
    WHERE admin_id IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.profile_reminder_settings') IS NOT NULL THEN
    UPDATE profile_reminder_settings
    SET updated_by = NULL
    WHERE updated_by IN (SELECT id FROM removed_accounts);
  END IF;

  IF to_regclass('public.profile_reminder_runs') IS NOT NULL THEN
    UPDATE profile_reminder_runs
    SET admin_id = NULL
    WHERE admin_id IN (SELECT id FROM removed_accounts);
  END IF;

  DELETE FROM accounts WHERE id IN (SELECT id FROM removed_accounts);

  IF to_regclass('public.registration_drafts') IS NOT NULL THEN
    DELETE FROM registration_drafts
    WHERE personal_email LIKE '%.sample@example.com'
       OR linked_student_id IN (SELECT student_id FROM removed_students)
       OR COALESCE(linked_student_id, '') LIKE 'SAMP-%';
  END IF;

  DELETE FROM university_records
  WHERE student_id IN (SELECT student_id FROM removed_students)
     OR student_id LIKE 'SAMP-%'
     OR personal_email LIKE '%.sample@example.com';

  CREATE TEMP TABLE sample_programs (
    slot int PRIMARY KEY,
    degree text NOT NULL,
    course_code text NOT NULL,
    college text NOT NULL,
    soc_code text NOT NULL,
    first_title text NOT NULL,
    first_employer text NOT NULL,
    present_title text NOT NULL,
    present_employer text NOT NULL,
    industry text NOT NULL,
    skills text NOT NULL,
    certification_name text NOT NULL,
    study_course text NOT NULL
  ) ON COMMIT DROP;

  INSERT INTO sample_programs (
    slot, degree, course_code, college, soc_code, first_title, first_employer,
    present_title, present_employer, industry, skills, certification_name, study_course
  )
  VALUES
    (1, 'BS Information Technology', 'BSIT', 'College of Computer Studies', '2512', 'Junior Software Developer', 'Pampanga Digital Labs', 'Software Engineer', 'North Luzon Systems Corp.', 'Information and communications technology', 'Python, SQL, React', 'IT Specialist', 'Master of Science in Information Technology'),
    (2, 'BS Computer Science', 'BSCS', 'College of Computer Studies', '2511', 'Junior Programmer', 'Clark Dev Studio', 'Systems Analyst', 'Angeles Tech Partners', 'Information and communications technology', 'Java, SQL, UML', 'IT Specialist', 'Master of Science in Computer Science'),
    (3, 'BS Nursing', 'BSN', 'College of Nursing', '2221', 'Staff Nurse', 'Angeles University Foundation Medical Center', 'Senior Staff Nurse', 'The Medical City Clark', 'Health', 'Patient Care, Clinical Documentation, IV Therapy', 'Basic Life Support', 'Master in Nursing'),
    (4, 'BS Accountancy', 'BSA', 'College of Business and Accountancy', '2411', 'Audit Associate', 'Reyes and Co. CPAs', 'Senior Auditor', 'Pampanga Audit Group', 'Finance and accounting', 'Audit, Excel, Financial Reporting', 'Certified Public Accountant Review Completion', 'Master in Business Administration'),
    (5, 'BS Civil Engineering', 'BSCE', 'College of Engineering and Architecture', '2142', 'Site Engineer', 'Kapampangan Builders Inc.', 'Civil Engineer', 'North Luzon Infrastructure', 'Construction', 'AutoCAD, Structural Design, Site Supervision', 'Project Supervision Certificate', 'Master of Science in Civil Engineering'),
    (6, 'BS Business Administration', 'BSBA', 'College of Business and Accountancy', '1221', 'Sales Associate', 'Marquee Retail Pampanga', 'Marketing Manager', 'Clark Freeport Brands', 'Sales and marketing', 'Sales, Brand Management, Customer Service', 'Marketing Practice Certificate', 'Master in Business Administration'),
    (7, 'Bachelor of Elementary Education', 'BEED', 'College of Education', '2341', 'Teacher Aide', 'Magalang Central School', 'Elementary Teacher', 'Angeles City Elementary School', 'Education', 'Lesson Planning, Classroom Management, Literacy', 'Licensure Examination for Teachers Review', 'Master of Arts in Education'),
    (8, 'BS Psychology', 'BSPSY', 'College of Arts and Sciences', '2634', 'HR Assistant', 'Pampanga People Partners', 'Guidance Associate', 'Holy Angel Learning Center', 'Education', 'Counseling, Assessment, Interviewing', 'Psychological First Aid', 'Master of Arts in Psychology'),
    (9, 'BS Hospitality Management', 'BSHM', 'College of Business and Accountancy', '1412', 'Front Office Associate', 'Clark Grand Hotel', 'Restaurant Manager', 'Clark Dining Co.', 'Hospitality and food service', 'Guest Service, Food Service, Reservations', 'Food Safety Handler', 'Master in Hospitality Management'),
    (10, 'BS Criminology', 'BSCRIM', 'College of Criminal Justice Education', '3355', 'Community Immersion Officer', 'Porac Municipal Station', 'Police Officer', 'Angeles City Police Station', 'Public safety', 'Community Policing, Report Writing, Investigation', 'Law Enforcement Orientation', 'Master in Public Safety'),
    (11, 'BS Medical Technology', 'BSMT', 'College of Allied Medical Professions', '3212', 'Laboratory Aide', 'AUF Medical Center Laboratory', 'Medical Technologist', 'The Medical City Clark Laboratory', 'Health', 'Clinical Microscopy, Hematology, Phlebotomy', 'Laboratory Quality Certificate', 'Master of Science in Medical Laboratory Science'),
    (12, 'BS Electronics Engineering', 'BSECE', 'College of Engineering and Architecture', '2152', 'Technician', 'Clark Assembly Plant', 'Electronics Engineer', 'North Luzon Devices', 'Manufacturing', 'Circuit Design, Testing, PLC', 'Electronics Assembly Certificate', 'Master of Engineering'),
    (13, 'Bachelor of Secondary Education', 'BSED', 'College of Education', '2330', 'Practice Teacher', 'Angeles City National High School', 'High School Teacher', 'Holy Angel Learning Center', 'Education', 'English Instruction, Assessment, Lesson Planning', 'Subject Teaching Certificate', 'Master of Arts in Education'),
    (14, 'BS Pharmacy', 'BSPHARM', 'College of Allied Medical Professions', '2262', 'Pharmacy Assistant', 'Generika Angeles', 'Pharmacist', 'Mercury Drug Angeles', 'Health', 'Dispensing, Patient Counseling, Inventory', 'Pharmacy Practice Certificate', 'Master in Pharmacy'),
    (15, 'AB Communication', 'ABCOMM', 'College of Arts and Sciences', '2431', 'Content Associate', 'Pampanga News Desk', 'Digital Marketing Specialist', 'Clark Creative Studio', 'Sales and marketing', 'Copywriting, Social Media, Editing', 'Digital Campaigns Certificate', 'Master of Arts in Communication'),
    (16, 'BS Architecture', 'BSARCH', 'College of Engineering and Architecture', '2161', 'Junior Architect', 'Pampanga Design Studio', 'Project Architect', 'North Luzon Design Group', 'Architecture', 'Sketching, AutoCAD, Revit', 'Design Studio Certificate', 'Master of Architecture');

  CREATE TEMP TABLE sample_alumni (
    n int PRIMARY KEY,
    student_id text UNIQUE,
    first_name text,
    middle_name text,
    last_name text,
    husband_surname text,
    email text UNIQUE,
    degree text,
    year_graduated text,
    course_code text,
    college text,
    account_status text,
    rejection_reason text,
    city text,
    birth_date date,
    guardian_type text,
    guardian_degree text,
    ever_employed text,
    time_to_job text,
    first_related text,
    find_job text,
    first_occ text,
    first_emp text,
    first_sal text,
    first_stat text,
    currently_employed text,
    present_is_first text,
    pres_occ text,
    pres_emp text,
    pres_stay text,
    present_related text,
    pres_sal text,
    pres_head text,
    pres_head_email text,
    reason_label text,
    unemployment_code text,
    unemployment_details text,
    study_course text,
    study_school text,
    study_address text,
    study_year text,
    study_graduated text,
    scholarship text,
    skills text,
    soc_code text,
    alignment text,
    card_status text,
    award_title text,
    seminar_title text,
    job_industry text,
    certification_name text,
    phone text,
    bio text,
    address text
  ) ON COMMIT DROP;

  INSERT INTO sample_alumni
  SELECT
    g.n,
    (2016 + ((g.n - 1) % 10))::text || '-' || lpad((8000 + g.n)::text, 4, '0'),
    first_names[1 + ((g.n - 1) % array_length(first_names, 1))],
    middle_names[1 + ((g.n * 3) % array_length(middle_names, 1))],
    last_names[1 + ((g.n * 5) % array_length(last_names, 1))],
    last_names[1 + ((g.n * 7) % array_length(last_names, 1))],
    lower(first_names[1 + ((g.n - 1) % array_length(first_names, 1))])
      || '.' || lower(replace(last_names[1 + ((g.n * 5) % array_length(last_names, 1))], ' ', ''))
      || '.' || lpad(g.n::text, 3, '0') || '.sample@example.com',
    p.degree,
    (2016 + ((g.n - 1) % 10))::text,
    p.course_code,
    p.college,
    CASE
      WHEN g.n % 23 = 0 THEN 'Rejected'
      WHEN g.n % 11 = 0 THEN 'Pending'
      ELSE 'Active'
    END,
    CASE
      WHEN g.n % 23 = 0 THEN 'Submitted documents did not match the graduate record on file. Please contact the Alumni Office.'
      ELSE ''
    END,
    cities[1 + ((g.n - 1) % array_length(cities, 1))],
    make_date((2016 + ((g.n - 1) % 10)) - 22, 1 + ((g.n - 1) % 12), 1 + ((g.n - 1) % 28)),
    guardians[1 + ((g.n - 1) % array_length(guardians, 1))],
    'Yes',
    'Yes',
    waits[1 + ((g.n - 1) % array_length(waits, 1))],
    CASE WHEN g.n % 9 = 0 AND g.n % 8 <> 0 THEN 'No' ELSE 'Yes' END,
    find_jobs[1 + ((g.n - 1) % array_length(find_jobs, 1))],
    p.first_title,
    p.first_employer,
    salaries[1 + ((g.n - 1) % array_length(salaries, 1))],
    job_stats[1 + ((g.n - 1) % array_length(job_stats, 1))],
    CASE WHEN g.n % 8 = 0 THEN 'No' ELSE 'Yes' END,
    'No',
    CASE
      WHEN g.n % 9 = 0 AND g.n % 8 <> 0 THEN 'Office Clerk'
      ELSE p.present_title
    END,
    CASE
      WHEN g.n % 9 = 0 AND g.n % 8 <> 0 THEN 'Angeles City Hall'
      ELSE p.present_employer
    END,
    ((1 + (g.n % 6))::text || ' year(s)'),
    CASE WHEN g.n % 9 = 0 AND g.n % 8 <> 0 THEN 'No' ELSE 'Yes' END,
    salaries[1 + (g.n % array_length(salaries, 1))],
    'Jordan Cruz',
    'supervisor.' || lpad(g.n::text, 3, '0') || '.sample@example.com',
    CASE
      WHEN g.n % 8 = 0 THEN reason_labels[1 + ((g.n / 8 - 1) % array_length(reason_labels, 1))]
      ELSE ''
    END,
    CASE
      WHEN g.n % 8 = 0 THEN reason_codes[1 + ((g.n / 8 - 1) % array_length(reason_codes, 1))]
      ELSE ''
    END,
    CASE
      WHEN g.n % 8 = 0 THEN 'Recorded during the sample tracer interview for this graduate.'
      ELSE ''
    END,
    p.study_course,
    'Angeles University Foundation',
    'MacArthur Highway, Angeles City, Pampanga',
    (2017 + ((g.n - 1) % 10))::text,
    CASE WHEN g.n % 2 = 0 THEN 'Yes' ELSE 'No' END,
    'AUF Alumni Scholarship',
    p.skills,
    CASE
      WHEN g.n % 9 = 0 AND g.n % 8 <> 0 THEN '4110'
      ELSE p.soc_code
    END,
    CASE
      WHEN g.n % 8 = 0 THEN 'Unknown'
      WHEN g.n % 9 = 0 THEN 'Misaligned'
      ELSE 'Aligned'
    END,
    CASE
      WHEN g.n % 23 = 0 OR g.n % 11 = 0 THEN 'NotYetApplied'
      ELSE cards[1 + ((g.n - 1) % array_length(cards, 1))]
    END,
    p.college || ' Service Award ' || (2016 + ((g.n - 1) % 10))::text,
    p.course_code || ' Career Seminar',
    CASE
      WHEN g.n % 9 = 0 AND g.n % 8 <> 0 THEN 'Public administration'
      ELSE p.industry
    END,
    p.certification_name,
    '+63 917 555 ' || lpad(g.n::text, 4, '0'),
    first_names[1 + ((g.n - 1) % array_length(first_names, 1))] || ' ' ||
      last_names[1 + ((g.n * 5) % array_length(last_names, 1))] ||
      ' is a ' || (2016 + ((g.n - 1) % 10))::text || ' ' || p.degree ||
      ' graduate of Angeles University Foundation.',
    (100 + g.n)::text || ' Sample Street, ' ||
      cities[1 + ((g.n - 1) % array_length(cities, 1))] || ', Pampanga'
  FROM generate_series(1, 100) AS g(n)
  JOIN sample_programs p ON p.slot = 1 + ((g.n - 1) % 16);

  INSERT INTO university_records (
    student_id, first_name, middle_name, last_name, personal_email, degree, year_graduated, course_code, college
  )
  SELECT student_id, first_name, middle_name, last_name, email, degree, year_graduated, course_code, college
  FROM sample_alumni;

  INSERT INTO accounts (
    personal_email, password_hash, linked_student_id, is_verified, status, role, rejection_reason,
    privacy_consent, password_changed_at, first_name, last_name, must_change_password, token_version,
    last_login_at, created_at, updated_at
  )
  SELECT
    email,
    sample_password,
    student_id,
    account_status = 'Active',
    account_status,
    'Alumni',
    rejection_reason,
    true,
    now(),
    first_name,
    last_name,
    false,
    0,
    CASE WHEN account_status = 'Active' THEN now() - (n || ' days')::interval ELSE NULL END,
    now() - (n || ' days')::interval,
    now()
  FROM sample_alumni;

  INSERT INTO alumni_profiles (
    account_id, first_name, middle_name, last_name, husband_surname, country_residence, degree, year_graduated,
    guardian_type, guardian_degree_completed, job_timeline_ready, phone, city, photo_path, photo_mime,
    cover_path, cover_mime, bio, address, no_employment_reason, employment_answer_before,
    currently_unemployed, unemployment_reason, unemployment_details, birth_date, resume_document,
    created_at, updated_at
  )
  SELECT
    a.id,
    s.first_name,
    s.middle_name,
    s.last_name,
    s.husband_surname,
    'Philippines',
    s.degree,
    s.year_graduated,
    s.guardian_type,
    true,
    true,
    s.phone,
    s.city,
    '',
    '',
    '',
    '',
    s.bio,
    s.address,
    CASE
      WHEN s.currently_employed = 'No' THEN s.reason_label || ': ' || s.unemployment_details
      ELSE ''
    END,
    'Yes',
    s.currently_employed = 'No',
    s.unemployment_code,
    s.unemployment_details,
    s.birth_date,
    json_build_object(
      'headline', s.pres_occ,
      'summary', s.bio,
      'email', s.email,
      'phone', s.phone,
      'location', s.address
    ),
    now(),
    now()
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO alumni_jobs (
    account_id, job_title, company, start_date, end_date, is_current, industry, location, salary_range, description
  )
  SELECT
    a.id, s.first_occ, s.first_emp,
    make_date(s.year_graduated::int, 7, 1),
    make_date(s.year_graduated::int + 1, 6, 30),
    false, s.job_industry, s.city, s.first_sal, 'First job after graduation.'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO alumni_jobs (
    account_id, job_title, company, start_date, end_date, is_current, industry, location, salary_range, description
  )
  SELECT
    a.id, s.pres_occ, s.pres_emp,
    make_date(s.year_graduated::int + 1, 7, 1),
    CASE WHEN s.currently_employed = 'Yes' THEN NULL ELSE make_date(s.year_graduated::int + 2, 12, 31) END,
    s.currently_employed = 'Yes',
    s.job_industry, s.city, s.pres_sal,
    CASE WHEN s.currently_employed = 'Yes' THEN 'Current role.' ELSE 'Most recent role.' END
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO alumni_skills (account_id, skill_name, category)
  SELECT a.id, trim(skill), 'Professional'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  CROSS JOIN LATERAL unnest(string_to_array(s.skills, ',')) AS skill
  WHERE trim(skill) <> '';

  INSERT INTO further_studies (
    account_id, course_degree, school, institution_address, year_enrolled, scholarship, is_graduated
  )
  SELECT
    a.id, s.study_course, s.study_school, s.study_address, s.study_year, s.scholarship,
    s.study_graduated = 'Yes'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO alumni_seminars (account_id, title, location, held_on, organizer)
  SELECT a.id, s.seminar_title, 'Angeles University Foundation', s.year_graduated || '-11-15', 'AAPS'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO alumni_awards (account_id, title, issuer, awarded_on, description)
  SELECT
    a.id, s.award_title, 'Angeles University Foundation', s.year_graduated || '-03-20',
    'Recognition recorded for the class of ' || s.year_graduated || '.'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO alumni_certifications (
    account_id, certification_name, issuing_organization, date_issued, awarded_on, skills_covered,
    is_verified, verification_url, certificate_path, certificate_mime, certificate_filename
  )
  SELECT
    a.id,
    s.certification_name,
    'Angeles University Foundation',
    make_date(s.year_graduated::int, 12, 1),
    s.year_graduated || '-12-01',
    COALESCE(
      (SELECT json_agg(trim(skill)) FROM unnest(string_to_array(s.skills, ',')) AS skill WHERE trim(skill) <> ''),
      '[]'::json
    ),
    true,
    'https://www.auf.edu.ph',
    '',
    '',
    ''
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO resumes (
    account_id, original_filename, stored_path, mime_type, extracted_text, parsed_json, parser_source, created_at
  )
  SELECT
    a.id,
    s.student_id || '.pdf',
    'sample-resumes/' || s.student_id || '.pdf',
    'application/pdf',
    s.bio || ' Skills: ' || s.skills || '. First role: ' || s.first_occ || ' at ' || s.first_emp || '.',
    json_build_object(
      'name', s.first_name || ' ' || s.middle_name || ' ' || s.last_name,
      'email', s.email,
      'phone', s.phone,
      'education', json_build_array(json_build_object('degree', s.degree, 'school', 'Angeles University Foundation', 'year', s.year_graduated)),
      'jobs', json_build_array(
        json_build_object('title', s.first_occ, 'employer', s.first_emp),
        json_build_object('title', s.pres_occ, 'employer', s.pres_emp)
      ),
      'skills', COALESCE(
        (SELECT json_agg(trim(skill)) FROM unnest(string_to_array(s.skills, ',')) AS skill WHERE trim(skill) <> ''),
        '[]'::json
      )
    ),
    'sample',
    now()
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO tracer_submissions (
    account_id, student_id, resume_id, data_json, extra_answers, survey_version,
    alignment_status, alignment_score, soc_code, submitted_at
  )
  SELECT
    a.id,
    s.student_id,
    r.id,
    json_build_object(
      'first_name', s.first_name,
      'middle_name', s.middle_name,
      'last_name', s.last_name,
      'husband_surname', s.husband_surname,
      'country', 'Philippines',
      'degree', s.degree,
      'year_graduated', s.year_graduated,
      'college', s.college,
      'course_code', s.course_code,
      'email', s.email,
      'phone', s.phone,
      'city', s.city,
      'address', s.address,
      'birth_date', to_char(s.birth_date, 'YYYY-MM-DD'),
      'primary_guardian', s.guardian_type,
      'guardian_degree_completed', s.guardian_degree,
      'ever_employed', s.ever_employed,
      'time_to_first_job', s.time_to_job,
      'first_related', s.first_related,
      'find_job', s.find_job,
      'first_occ', s.first_occ,
      'first_emp', s.first_emp,
      'first_sal', s.first_sal,
      'first_stat', s.first_stat,
      'is_currently_employed', s.currently_employed,
      'present_job_is_first', s.present_is_first,
      'pres_occ', s.pres_occ,
      'pres_emp', s.pres_emp,
      'pres_head', s.pres_head,
      'pres_head_email', s.pres_head_email,
      'pres_stay', s.pres_stay,
      'present_related_degree', s.present_related,
      'reason_current', CASE WHEN s.reason_label <> '' THEN json_build_array(s.reason_label) ELSE '[]'::json END,
      'reason_current_other', CASE WHEN s.unemployment_code = 'other' THEN s.unemployment_details ELSE '' END,
      'enroll_further_studies', 'Yes',
      'further_studies', json_build_array(json_build_object(
        'course_degree', s.study_course,
        'school', s.study_school,
        'institution_address', s.study_address,
        'year_enrolled', s.study_year,
        'scholarship', s.scholarship,
        'is_graduated', s.study_graduated
      )),
      'participated_seminars', 'Yes',
      'seminars_helpful', 'Yes',
      'mentoring_rating', 4,
      'advocacy_rating', 4,
      'volunteering_rating', 3,
      'engagement_desc', 'AUF career activities helped this graduate prepare for work.',
      'curriculum_suggestions', json_build_object('develop_competencies', 'More practicum and industry projects'),
      'skills', COALESCE(
        (SELECT json_agg(trim(skill)) FROM unnest(string_to_array(s.skills, ',')) AS skill WHERE trim(skill) <> ''),
        '[]'::json
      ),
      'current_occupation', s.pres_occ,
      'current_employer', s.pres_emp,
      'award_title', s.award_title,
      'seminar_title', s.seminar_title,
      'certification_name', s.certification_name
    ),
    json_build_object('ojt_helpfulness', 4, 'work_arrangement', 'Hybrid'),
    (SELECT published_version FROM survey_definitions WHERE slug = 'gts' LIMIT 1),
    s.alignment,
    CASE s.alignment WHEN 'Aligned' THEN 100 WHEN 'Misaligned' THEN 0 ELSE 50 END,
    s.soc_code,
    now() - (s.n || ' days')::interval
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  JOIN resumes r ON r.account_id = a.id;

  INSERT INTO alignment_results (
    account_id, overall_match_score, alignment_justification, justification_detail, suggested_career_paths, last_updated
  )
  SELECT
    a.id,
    CASE s.alignment WHEN 'Aligned' THEN 100 WHEN 'Misaligned' THEN 0 ELSE 50 END,
    s.alignment,
    CASE s.alignment
      WHEN 'Aligned' THEN s.degree || ' matches the recorded occupation ' || s.pres_occ || '.'
      WHEN 'Misaligned' THEN 'The recorded occupation ' || s.pres_occ || ' sits outside the usual path for ' || s.degree || '.'
      ELSE 'The latest employment status is not currently employed, so alignment is unknown.'
    END,
    json_build_array(s.pres_occ, s.first_occ),
    now()
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO alumni_cards (
    account_id, status, card_number, issued_at, expires_at, submitted_at, pickup_ready_at,
    pickup_location, application_json
  )
  SELECT
    a.id,
    s.card_status,
    'AUF-' || s.student_id,
    now() - interval '20 days',
    DATE '2030-03-31',
    now() - interval '40 days',
    now() - interval '10 days',
    'AAPS, AUF Main Campus',
    json_build_object(
      'membership_type', 'New',
      'student_number', s.student_id,
      'email', s.email,
      'phone', s.phone,
      'first_name', s.first_name,
      'middle_name', s.middle_name,
      'last_name', s.last_name,
      'husband_surname', s.husband_surname,
      'birth_date', to_char(s.birth_date, 'YYYY-MM-DD'),
      'address', s.address,
      'year_graduated', s.year_graduated,
      'college', s.college,
      'course', s.degree,
      'course_code', s.course_code,
      'appointment_location', 'AAPS, AUF Main Campus'
    )
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  INSERT INTO alumni_notifications (account_id, title, body, category, created_at, read_at, link)
  SELECT
    a.id,
    'Profile record is ready',
    'Your CareerSense profile, tracer record, and alumni card details are on file with AAPS.',
    'announcement',
    now(),
    CASE WHEN s.n % 2 = 0 THEN now() ELSE NULL END,
    '/alumni'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email;

  IF to_regclass('public.badge_definitions') IS NOT NULL AND to_regclass('public.alumni_badges') IS NOT NULL THEN
    INSERT INTO alumni_badges (account_id, badge_key, awarded_at, award_metadata)
    SELECT a.id, b.key, now(), json_build_object('source', 'sample')
    FROM sample_alumni s
    JOIN accounts a ON a.personal_email = s.email
    JOIN badge_definitions b ON b.key IN ('profile_complete', 'tracer_completed', 'career_updated')
    WHERE s.account_status = 'Active';

    INSERT INTO alumni_badges (account_id, badge_key, awarded_at, award_metadata)
    SELECT a.id, 'alumni_card_holder', now(), json_build_object('source', 'sample')
    FROM sample_alumni s
    JOIN accounts a ON a.personal_email = s.email
    WHERE s.card_status = 'Claimed'
      AND EXISTS (SELECT 1 FROM badge_definitions b WHERE b.key = 'alumni_card_holder');
  END IF;

  IF to_regclass('public.alumni_perks') IS NOT NULL AND to_regclass('public.alumni_perk_redemptions') IS NOT NULL THEN
    INSERT INTO alumni_perk_redemptions (account_id, perk_id, redeemed_at, code)
    SELECT a.id, perk.id, now() - (s.n || ' days')::interval, 'AUF-PR-' || lpad(s.n::text, 4, '0')
    FROM sample_alumni s
    JOIN accounts a ON a.personal_email = s.email
    JOIN LATERAL (SELECT id FROM alumni_perks ORDER BY id LIMIT 1) AS perk ON true
    WHERE s.account_status = 'Active' AND s.n % 2 = 0;
  END IF;

  IF to_regclass('public.partner_activities') IS NOT NULL THEN
    INSERT INTO partner_activities (
      alumni_account_id, activity_type, recording_method, status, partner_name,
      benefit_label, activity_at, notes, reference_code, outcome_detail,
      token_fingerprint, idempotency_key, recorded_by_id, created_at, updated_at
    )
    SELECT
      a.id,
      'qr_scan',
      'qr_scan',
      'success',
      'AAPS Partner Desk',
      'Alumni QR verified',
      now() - (s.n || ' days')::interval,
      'Sample QR scan for ' || s.first_name || ' ' || s.last_name || '.',
      'QR-' || s.student_id,
      'Identity matched',
      md5(s.student_id),
      'sample-qr-' || s.student_id,
      (SELECT id FROM accounts WHERE role = 'Admin' ORDER BY id LIMIT 1),
      now(),
      now()
    FROM sample_alumni s
    JOIN accounts a ON a.personal_email = s.email
    WHERE s.account_status = 'Active';
  END IF;

  RAISE NOTICE 'Sample alumni loaded: %', (SELECT count(*) FROM sample_alumni);
END
$seed$;

SELECT
  (SELECT count(*) FROM accounts WHERE role = 'Admin') AS admins_kept,
  (SELECT count(*) FROM accounts WHERE personal_email LIKE '%.sample@example.com') AS sample_accounts,
  (SELECT count(*) FROM university_records WHERE personal_email LIKE '%.sample@example.com') AS sample_registry,
  (SELECT count(*) FROM tracer_submissions t
     JOIN accounts a ON a.id = t.account_id
    WHERE a.personal_email LIKE '%.sample@example.com') AS sample_tracers;

COMMIT;
