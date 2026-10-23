-- CareerSense sample data for Render PostgreSQL.
-- Paste this whole script into the Render Postgres shell (psql). It is one statement.
--
-- Inserts 40 complete graduate records: registry row, Active/Pending/Rejected
-- account, profile, Graduate Tracer Survey, jobs, skills, alignment, alumni card,
-- and any further study, seminar, or award listed for that graduate.
--
-- Sample alumni password: Alumni@2026
-- Emails look like andrea.bautista.sample@example.com
-- Student numbers start with SAMP- so they stay separate from registrar imports.
-- Existing administrators and non-sample rows are left unchanged.
-- Running the script again does not duplicate these rows.

DO $seed$
DECLARE
  sample_password text := '$2b$12$lr2i8fYccLPIYvuOuHL0A.P27ZU54pYfRw0wiaw1F7YC5aPkg/Uoi';
  registry_count integer;
  account_count integer;
  tracer_count integer;
BEGIN
  INSERT INTO soc_codes (soc_code, code, description, title_patterns, degree_patterns, category, major_group)
  SELECT * FROM (VALUES
    ('1330', '1330', 'Information and Communications Technology Service Managers', 'it manager,information technology manager', 'information technology,computer science', 'ICT', ''),
    ('2512', '2512', 'Software Developers', 'software developer,software engineer,web developer,programmer', 'information technology,computer science,computer engineering', 'ICT', ''),
    ('2511', '2511', 'Systems Analysts', 'systems analyst,it analyst', 'information technology,computer science', 'ICT', ''),
    ('2522', '2522', 'Systems Administrators', 'systems administrator,it support specialist', 'information technology,computer science', 'ICT', ''),
    ('3512', '3512', 'Information and Communications Technology User Support Technicians', 'it support,computer technician', 'information technology,computer science', 'ICT', ''),
    ('2411', '2411', 'Accountants', 'accountant,auditor,bookkeeper', 'accountancy,accounting', 'Business and Administration', ''),
    ('1211', '1211', 'Finance Managers', 'finance manager,accounting manager', 'accountancy,finance', 'Business and Administration', ''),
    ('1221', '1221', 'Sales and Marketing Managers', 'sales manager,marketing manager', 'marketing,business administration', 'Sales and Marketing', ''),
    ('2221', '2221', 'Nursing Professionals', 'staff nurse,registered nurse', 'nursing', 'Health', ''),
    ('2341', '2341', 'Primary School Teachers', 'elementary teacher,primary school teacher', 'elementary education,education', 'Education', ''),
    ('2330', '2330', 'Secondary Education Teachers', 'high school teacher,secondary teacher', 'secondary education,education', 'Education', ''),
    ('2142', '2142', 'Civil Engineers', 'civil engineer,site engineer', 'civil engineering', 'Engineering', ''),
    ('2152', '2152', 'Electronics Engineers', 'electronics engineer', 'electronics engineering', 'Engineering', ''),
    ('2161', '2161', 'Building Architects', 'architect,junior architect', 'architecture', 'Engineering', ''),
    ('1412', '1412', 'Restaurant Managers', 'restaurant manager,front office', 'hospitality management', 'Hospitality', ''),
    ('2431', '2431', 'Advertising and Marketing Professionals', 'marketing specialist,content associate', 'communication,marketing', 'Sales and Marketing', ''),
    ('2634', '2634', 'Psychologists', 'psychologist,guidance associate,hr assistant', 'psychology', 'Social Sciences', ''),
    ('3212', '3212', 'Medical and Pathology Laboratory Technicians', 'medical technologist,laboratory aide', 'medical technology', 'Health', ''),
    ('2262', '2262', 'Pharmacists', 'pharmacist,pharmacy assistant', 'pharmacy', 'Health', ''),
    ('1120', '1120', 'Managing Directors and Chief Executives', 'store owner,managing director', 'business administration', 'Management', ''),
    ('4110', '4110', 'General Office Clerks', 'office clerk,office staff,encoder', 'business administration,office administration', 'Clerical', ''),
    ('3355', '3355', 'Police Officers', 'police officer', 'criminology', 'Public safety', '')
  ) AS v(soc_code, code, description, title_patterns, degree_patterns, category, major_group)
  WHERE NOT EXISTS (
    SELECT 1 FROM soc_codes c WHERE c.soc_code = v.soc_code OR c.code = v.code
  );

  IF to_regclass('sample_alumni') IS NOT NULL THEN
    DROP TABLE sample_alumni;
  END IF;
  CREATE TEMP TABLE sample_alumni (
    student_id text PRIMARY KEY,
    first_name text,
    middle_name text,
    last_name text,
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
    reason_current text,
    unemployment_code text,
    enroll_further text,
    study_course text,
    study_school text,
    study_year text,
    study_graduated text,
    skills text,
    soc_code text,
    alignment text,
    card_status text,
    award_title text,
    seminar_title text,
    job_industry text,
    email text
  ) ON COMMIT DROP;

  INSERT INTO sample_alumni (
    student_id, first_name, middle_name, last_name, degree, year_graduated, course_code, college,
    account_status, rejection_reason, city, birth_date, guardian_type, guardian_degree,
    ever_employed, time_to_job, first_related, find_job, first_occ, first_emp, first_sal, first_stat,
    currently_employed, present_is_first, pres_occ, pres_emp, pres_stay, present_related, pres_sal,
    reason_current, unemployment_code, enroll_further, study_course, study_school, study_year,
    study_graduated, skills, soc_code, alignment, card_status, award_title, seminar_title, job_industry
  )
  VALUES
('SAMP-2019-001', 'Andrea', 'Santos', 'Bautista', 'BS Information Technology', '2019', 'BSIT', 'College of Computer Studies', 'Active', '', 'Angeles City', '1997-03-12', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Recommended by someone', 'Junior Software Developer', 'Pampanga Digital Labs', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'No', 'Software Engineer', 'North Luzon Systems Corp.', '5 year(s)', 'Yes', '₱41,400 to ₱55,199', '', '', 'No', '', '', '', '', 'Python, SQL, React, Git', '2512', 'Aligned', 'Claimed', 'College Service Award', 'Cloud Career Seminar', 'Information and communications technology'),
('SAMP-2019-002', 'Rafael', 'Cruz', 'Mendoza', 'BS Computer Science', '2019', 'BSCS', 'College of Computer Studies', 'Active', '', 'San Fernando', '1997-07-04', 'Father', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Arranged by AUF', 'Junior Programmer', 'Clark Dev Studio', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'No', 'Systems Analyst', 'Angeles Tech Partners', '4 year(s)', 'Yes', '₱55,200 to ₱68,999', '', '', 'No', '', '', '', '', 'Java, SQL, UML', '2511', 'Aligned', 'Claimed', '', 'Systems Analysis Workshop', 'Information and communications technology'),
('SAMP-2019-003', 'Camille', 'Reyes', 'Flores', 'BS Nursing', '2019', 'BSN', 'College of Nursing', 'Active', '', 'Angeles City', '1997-01-19', 'Both Parents', 'Yes', 'Yes', 'Less than a month', 'Yes', 'Arranged by AUF', 'Staff Nurse', 'Angeles University Foundation Medical Center', '₱27,600 to ₱41,399', 'Regular/Permanent', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Patient Care, Clinical Documentation', '2221', 'Aligned', 'Claimed', 'Clinical Excellence Citation', 'Basic Life Support Update', 'Health'),
('SAMP-2019-004', 'Dominic', 'Garcia', 'Villanueva', 'BS Accountancy', '2019', 'BSA', 'College of Business and Accountancy', 'Active', '', 'Mabalacat', '1996-11-02', 'Mother', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Recommended by someone', 'Audit Associate', 'Reyes and Co. CPAs', '₱27,600 to ₱41,399', 'Regular/Permanent', 'Yes', 'No', 'Senior Auditor', 'Pampanga Audit Group', '3 year(s)', 'Yes', '₱55,200 to ₱68,999', '', '', 'Yes', 'Master in Business Administration', 'Angeles University Foundation', '2023', 'No', 'Audit, Excel, Financial Reporting', '2411', 'Aligned', 'Claimed', '', '', 'Finance and accounting'),
('SAMP-2019-005', 'Isabelle', 'Lim', 'Navarro', 'BS Civil Engineering', '2019', 'BSCE', 'College of Engineering and Architecture', 'Active', '', 'Porac', '1997-05-28', 'Both Parents', 'No', 'Yes', '7 to 11 months', 'Yes', 'As walk-in applicant', 'Site Engineer', 'Kapampangan Builders Inc.', '₱27,600 to ₱41,399', 'Contractual/Casual', 'Yes', 'No', 'Civil Engineer', 'North Luzon Infrastructure', '4 year(s)', 'Yes', '₱41,400 to ₱55,199', '', '', 'No', '', '', '', '', 'AutoCAD, Structural Design, Site Supervision', '2142', 'Aligned', 'ReadyForPickup', '', 'Project Management Seminar', 'Construction'),
('SAMP-2020-006', 'Paolo', 'Diaz', 'Santos', 'BS Business Administration', '2020', 'BSBA', 'College of Business and Accountancy', 'Active', '', 'Angeles City', '1998-02-14', 'Father', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Response to an advertisement', 'Sales Associate', 'Marquee Retail Pampanga', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'No', 'Marketing Manager', 'Clark Freeport Brands', '3 year(s)', 'Yes', '₱55,200 to ₱68,999', '', '', 'No', '', '', '', '', 'Sales, Brand Management', '1221', 'Aligned', 'Claimed', 'Alumni Homecoming Volunteer', '', 'Sales and marketing'),
('SAMP-2020-007', 'Hanna', 'Torres', 'Cruz', 'Bachelor of Elementary Education', '2020', 'BEED', 'College of Education', 'Active', '', 'Magalang', '1998-09-09', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Arranged by AUF', 'Elementary Teacher', 'Angeles City Elementary School', '₱13,800 to ₱27,599', 'Regular/Permanent', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Lesson Planning, Classroom Management', '2341', 'Aligned', 'Claimed', '', 'Literacy Teaching Circle', 'Education'),
('SAMP-2020-008', 'Miguel', 'Bautista', 'Ramos', 'BS Psychology', '2020', 'BSPSY', 'College of Arts and Sciences', 'Active', '', 'San Fernando', '1998-04-21', 'Mother', 'Yes', 'Yes', '7 to 11 months', 'Yes', 'Recommended by someone', 'HR Assistant', 'Pampanga People Partners', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'No', 'Guidance Associate', 'Holy Angel Learning Center', '2 year(s)', 'Yes', '₱27,600 to ₱41,399', '', '', 'Yes', 'Master of Arts in Psychology', 'Angeles University Foundation', '2023', 'No', 'Counseling, Assessment', '2634', 'Aligned', 'Claimed', '', '', 'Education'),
('SAMP-2020-009', 'Sofia', 'Pineda', 'Garcia', 'BS Hospitality Management', '2020', 'BSHM', 'College of Business and Accountancy', 'Active', '', 'Angeles City', '1998-12-01', 'Both Parents', 'No', 'Yes', '1 to 6 months', 'Yes', 'As walk-in applicant', 'Restaurant Supervisor', 'Kapampangan Kitchen Group', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'No', 'Restaurant Manager', 'Clark Dining Co.', '3 year(s)', 'Yes', '₱41,400 to ₱55,199', '', '', 'No', '', '', '', '', 'Food Service, Guest Relations', '1412', 'Aligned', 'Approved', '', 'Hospitality Supervisors Forum', 'Hospitality and food service'),
('SAMP-2020-010', 'Carlo', 'Villanueva', 'Lopez', 'BS Criminology', '2020', 'BSCRIM', 'College of Criminal Justice Education', 'Active', '', 'Mexico', '1997-08-16', 'Father', 'No', 'Yes', '7 to 11 months', 'Yes', 'Public Employment Service Office / Job Fair', 'Police Officer', 'Angeles City Police Station', '₱27,600 to ₱41,399', 'Regular/Permanent', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Community Policing, Report Writing', '3355', 'Aligned', 'Claimed', 'Community Service Medal', '', 'Public safety'),
('SAMP-2020-011', 'Jasmine', 'Aquino', 'Dela Cruz', 'BS Medical Technology', '2020', 'BSMT', 'College of Allied Medical Professions', 'Active', '', 'Mabalacat', '1998-06-30', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Arranged by AUF', 'Medical Technologist', 'AUF Medical Center Laboratory', '₱27,600 to ₱41,399', 'Regular/Permanent', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Clinical Microscopy, Hematology', '3212', 'Aligned', 'Claimed', '', 'Laboratory Quality Seminar', 'Health'),
('SAMP-2021-012', 'Nathan', 'Reyes', 'Tan', 'BS Electronics Engineering', '2021', 'BSECE', 'College of Engineering and Architecture', 'Active', '', 'Clark', '1999-03-03', 'Father', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Response to an advertisement', 'Electronics Engineer', 'Clark Electronics Manufacturing', '₱27,600 to ₱41,399', 'Regular/Permanent', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Circuit Design, Testing', '2152', 'Aligned', 'ForVerification', '', '', 'Manufacturing'),
('SAMP-2021-013', 'Bianca', 'Santos', 'Ong', 'Bachelor of Secondary Education', '2021', 'BSED', 'College of Education', 'Active', '', 'Angeles City', '1999-10-11', 'Mother', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Recommended by someone', 'High School Teacher', 'Angeles City National High School', '₱13,800 to ₱27,599', 'Regular/Permanent', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'English Instruction, Assessment', '2330', 'Aligned', 'Claimed', 'Outstanding Teacher Citation', 'Subject Teaching Workshop', 'Education'),
('SAMP-2021-014', 'Leo', 'Mendoza', 'Chua', 'BS Pharmacy', '2021', 'BSPHARM', 'College of Allied Medical Professions', 'Active', '', 'San Fernando', '1999-01-25', 'Both Parents', 'Yes', 'Yes', '7 to 11 months', 'Yes', 'As walk-in applicant', 'Pharmacist', 'Mercury Drug Angeles', '₱27,600 to ₱41,399', 'Regular/Permanent', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Dispensing, Patient Counseling', '2262', 'Aligned', 'Claimed', '', '', 'Health'),
('SAMP-2021-015', 'Patricia', 'Flores', 'Lim', 'AB Communication', '2021', 'ABCOMM', 'College of Arts and Sciences', 'Active', '', 'Angeles City', '1999-05-17', 'Mother', 'No', 'Yes', '1 to 6 months', 'Yes', 'Information from friends', 'Marketing Associate', 'North Luzon Media', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'No', 'Digital Marketing Specialist', 'Clark Creative Studio', '2 year(s)', 'Yes', '₱27,600 to ₱41,399', '', '', 'No', '', '', '', '', 'Copywriting, Social Media', '2431', 'Aligned', 'ReadyForPickup', '', 'Digital Campaigns Seminar', 'Sales and marketing'),
('SAMP-2021-016', 'Gabriel', 'Cruz', 'Santos', 'BS Computer Engineering', '2021', 'BSCPE', 'College of Engineering and Architecture', 'Active', '', 'Mabalacat', '1999-08-08', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Arranged by AUF', 'Junior Software Developer', 'Pampanga Systems Inc.', '₱27,600 to ₱41,399', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'C, Python, Embedded Systems', '2512', 'Aligned', 'Claimed', '', '', 'Information and communications technology'),
('SAMP-2021-017', 'Elena', 'Navarro', 'Reyes', 'BS Information Technology', '2021', 'BSIT', 'College of Computer Studies', 'Active', '', 'Angeles City', '1999-02-02', 'Father', 'No', 'Yes', 'Less than a month', 'Yes', 'Public Employment Service Office / Job Fair', 'IT Support Specialist', 'Angeles Medical Center', '₱13,800 to ₱27,599', 'Contractual/Casual', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Troubleshooting, Networking', '3512', 'Aligned', 'Approved', '', 'Help Desk Skills Day', 'Information and communications technology'),
('SAMP-2022-018', 'Marco', 'Garcia', 'Bautista', 'BS Accountancy', '2022', 'BSA', 'College of Business and Accountancy', 'Active', '', 'Angeles City', '2000-04-18', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Family business', 'Associate Auditor', 'Reyes and Co. CPAs', '₱27,600 to ₱41,399', 'Regular/Permanent', 'Yes', 'No', 'Restaurant Manager', 'Kapampangan Kitchen Group', '2 year(s)', 'No', '₱41,400 to ₱55,199', '', '', 'Yes', 'Master in Business Administration', 'Angeles University Foundation', '2024', 'No', 'Audit, Operations, Excel', '1412', 'Misaligned', 'NotYetApplied', '', '', 'Hospitality and food service'),
('SAMP-2022-019', 'Chloe', 'Lim', 'Villanueva', 'BS Nursing', '2022', 'BSN', 'College of Nursing', 'Active', '', 'Porac', '2000-07-07', 'Mother', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Arranged by AUF', 'Staff Nurse', 'The Medical City Clark', '₱27,600 to ₱41,399', 'Regular/Permanent', 'Yes', 'Yes', '', '', '', '', '', '', '', 'Yes', 'Master in Nursing', 'Angeles University Foundation', '2024', 'No', 'Patient Care, IV Therapy', '2221', 'Aligned', 'Claimed', '', 'Maternal and Child Care Update', 'Health'),
('SAMP-2022-020', 'Adrian', 'Torres', 'Flores', 'BS Civil Engineering', '2022', 'BSCE', 'College of Engineering and Architecture', 'Active', '', 'Bacolor', '2000-09-23', 'Father', 'No', 'Yes', '7 to 11 months', 'Yes', 'As walk-in applicant', 'Junior Site Engineer', 'Pampanga Roads JV', '₱13,800 to ₱27,599', 'Contractual/Casual', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Surveying, AutoCAD', '2142', 'Aligned', 'ReadyForPickup', '', '', 'Construction'),
('SAMP-2022-021', 'Nina', 'Ramos', 'Pineda', 'BS Business Administration', '2022', 'BSBA', 'College of Business and Accountancy', 'Active', '', 'Angeles City', '2000-01-30', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Family business', 'Store Owner', 'Nina Home Bakes', '₱27,600 to ₱41,399', 'Self-Employed', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Bookkeeping, Customer Service', '1120', 'Aligned', 'Claimed', 'Young Entrepreneur Citation', '', 'Retail'),
('SAMP-2022-022', 'Justin', 'Santos', 'Aquino', 'BS Computer Science', '2022', 'BSCS', 'College of Computer Studies', 'Active', '', 'Clark', '2000-11-11', 'Father', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Response to an advertisement', 'Software Developer', 'North Luzon Systems Corp.', '₱27,600 to ₱41,399', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Python, JavaScript, SQL', '2512', 'Aligned', 'ForVerification', '', 'Campus Developer Meetup', 'Information and communications technology'),
('SAMP-2023-023', 'Ethan', 'Bautista', 'Cruz', 'BS Information Technology', '2023', 'BSIT', 'College of Computer Studies', 'Active', '', 'Mabalacat', '2001-06-06', 'Both Parents', 'No', 'Yes', '1 to 6 months', 'Yes', 'Recommended by someone', 'Junior Web Developer', 'Clark Web Works', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'HTML, CSS, JavaScript', '2512', 'Aligned', 'Claimed', '', '', 'Information and communications technology'),
('SAMP-2023-024', 'Mika', 'Dela Cruz', 'Tan', 'BS Nursing', '2023', 'BSN', 'College of Nursing', 'Rejected', 'Submitted documents did not match the graduate record on file. Please contact OAAPS.', 'Angeles City', '2001-02-20', 'Mother', 'Yes', 'Yes', '7 to 11 months', 'Yes', 'As walk-in applicant', 'Staff Nurse', 'Sacred Heart Medical Center', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Patient Care, Vital Signs', '2221', 'Aligned', 'NotYetApplied', '', '', 'Health'),
('SAMP-2023-025', 'Rosa', 'Lim', 'Aquino', 'BS Accountancy', '2023', 'BSA', 'College of Business and Accountancy', 'Pending', '', 'San Fernando', '2001-08-15', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Arranged by AUF', 'Accounting Staff', 'Santos Bookkeeping Services', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Bookkeeping, Excel, Taxation', '2411', 'Aligned', 'ForVerification', '', 'CPA Review Orientation', 'Finance and accounting'),
('SAMP-2024-026', 'Theo', 'Flores', 'Chua', 'BS Computer Engineering', '2024', 'BSCPE', 'College of Engineering and Architecture', 'Pending', '', 'Clark', '2002-03-09', 'Father', 'Yes', 'Yes', 'Less than a month', 'Yes', 'Public Employment Service Office / Job Fair', 'Associate Software Engineer', 'Angeles Firmware Lab', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'C, Python, Debugging', '2512', 'Aligned', 'NotYetApplied', '', '', 'Information and communications technology'),
('SAMP-2024-027', 'Julia', 'Navarro', 'Bautista', 'AB Communication', '2024', 'ABCOMM', 'College of Arts and Sciences', 'Pending', '', 'Angeles City', '2002-05-05', 'Mother', 'No', 'Yes', '1 to 6 months', 'Yes', 'Response to an advertisement', 'Content Associate', 'Pampanga News Desk', '₱13,800 to ₱27,599', 'Contractual/Casual', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Writing, Editing, Social Media', '2431', 'Aligned', 'NotYetApplied', '', '', 'Media'),
('SAMP-2024-028', 'Kyle', 'Reyes', 'Flores', 'BS Information Technology', '2024', 'BSIT', 'College of Computer Studies', 'Active', '', 'Mexico', '2002-10-19', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Information from friends', 'Office Clerk', 'Angeles City Hall', 'Below ₱13,800', 'Contractual/Casual', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Filing, Encoding, Microsoft Office', '4110', 'Misaligned', 'NotYetApplied', '', '', 'Public administration'),
('SAMP-2022-029', 'Lara', 'Dela Cruz', 'Mendoza', 'BS Psychology', '2022', 'BSPSY', 'College of Arts and Sciences', 'Active', '', 'Angeles City', '2000-12-12', 'Mother', 'Yes', 'Yes', '1 year to less than 2 years', 'Yes', 'Recommended by someone', 'HR Assistant', 'Clark Staffing Office', '₱13,800 to ₱27,599', 'Contractual/Casual', 'No', '', '', '', '', '', '', 'Looking for a job, but cannot find one', 'seeking', 'No', '', '', '', '', 'Interviewing, Records', '2634', 'Aligned', 'NotYetApplied', '', '', 'Human resources'),
('SAMP-2024-030', 'Mia', 'Flores', 'Navarro', 'BS Nursing', '2024', 'BSN', 'College of Nursing', 'Active', '', 'Mabalacat', '2002-01-08', 'Both Parents', 'Yes', 'No', '', '', '', '', '', '', '', 'No', '', '', '', '', '', '', 'Board or Licensure Examination Preparation', 'other', 'No', '', '', '', '', 'Anatomy, Patient Care', '', 'Unknown', 'NotYetApplied', '', 'Nursing Licensure Review', 'Health'),
('SAMP-2023-031', 'Grace', 'Ong', 'Reyes', 'Bachelor of Elementary Education', '2023', 'BEED', 'College of Education', 'Active', '', 'Magalang', '2001-04-04', 'Mother', 'Yes', 'Yes', '7 to 11 months', 'Yes', 'Arranged by AUF', 'Teacher Aide', 'Magalang Central School', 'Below ₱13,800', 'Contractual/Casual', 'No', '', '', '', '', '', '', 'Family-related reason/s', 'personal_family', 'No', '', '', '', '', 'Lesson Planning, Child Care', '2341', 'Aligned', 'NotYetApplied', '', '', 'Education'),
('SAMP-2021-032', 'Samuel', 'Chua', 'Lim', 'BS Pharmacy', '2021', 'BSPHARM', 'College of Allied Medical Professions', 'Active', '', 'San Fernando', '1999-09-14', 'Father', 'No', 'Yes', '1 to 6 months', 'Yes', 'As walk-in applicant', 'Pharmacy Assistant', 'Generika Angeles', '₱13,800 to ₱27,599', 'Contractual/Casual', 'No', '', '', '', '', '', '', 'Health-related reason/s', 'health', 'No', '', '', '', '', 'Dispensing, Inventory', '2262', 'Aligned', 'ForRenewal', '', '', 'Health'),
('SAMP-2025-033', 'Ivan', 'Mendoza', 'Dela Cruz', 'BS Computer Science', '2025', 'BSCS', 'College of Computer Studies', 'Active', '', 'Angeles City', '2003-07-22', 'Both Parents', 'Yes', 'No', '', '', '', '', '', '', '', 'No', '', '', '', '', '', '', 'Not Currently Seeking Employment', 'not_seeking', 'No', '', '', '', '', 'Python, Algorithms', '', 'Unknown', 'NotYetApplied', '', '', 'Information and communications technology'),
('SAMP-2023-034', 'Diana', 'Pineda', 'Santos', 'BS Medical Technology', '2023', 'BSMT', 'College of Allied Medical Professions', 'Active', '', 'Angeles City', '2001-03-27', 'Mother', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Arranged by AUF', 'Laboratory Aide', 'AUF Medical Center Laboratory', '₱13,800 to ₱27,599', 'Contractual/Casual', 'No', '', '', '', '', '', '', 'Continuing Education', 'further_studies', 'Yes', 'Master of Science in Medical Laboratory Science', 'Angeles University Foundation', '2024', 'No', 'Phlebotomy, Quality Control', '3212', 'Aligned', 'NotYetApplied', '', '', 'Health'),
('SAMP-2024-035', 'Felix', 'Aquino', 'Torres', 'BS Criminology', '2024', 'BSCRIM', 'College of Criminal Justice Education', 'Active', '', 'Porac', '2002-08-08', 'Father', 'No', 'No', '', '', '', '', '', '', '', 'No', '', '', '', '', '', '', 'Apprenticeship/Volunteer Work', 'other', 'No', '', '', '', '', 'Community Immersion, Report Writing', '', 'Unknown', 'NotYetApplied', '', 'Barangay Volunteer Immersion', 'Public safety'),
('SAMP-2020-036', 'Noel', 'Santos', 'Tan', 'BS Business Administration', '2020', 'BSBA', 'College of Business and Accountancy', 'Active', '', 'Bacolor', '1998-05-16', 'Other', 'No', 'Yes', '2 years to less than 3 years', 'No', 'Response to an advertisement', 'Office Staff', 'Bacolor Municipal Office', '₱13,800 to ₱27,599', 'Contractual/Casual', 'No', '', '', '', '', '', '', 'Other', 'other', 'No', '', '', '', '', 'Clerical Support, Encoding', '4110', 'Misaligned', 'NotYetApplied', '', '', 'Public administration'),
('SAMP-2024-037', 'Hannah', 'Cruz', 'Ramos', 'BS Architecture', '2024', 'BSARCH', 'College of Engineering and Architecture', 'Active', '', 'Angeles City', '2001-11-29', 'Both Parents', 'Yes', 'Yes', '1 to 6 months', 'Yes', 'Recommended by someone', 'Junior Architect', 'Pampanga Design Studio', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Sketching, AutoCAD, Revit', '2161', 'Aligned', 'ReadyForPickup', '', 'Design Studio Critique', 'Architecture'),
('SAMP-2025-038', 'Lena', 'Garcia', 'Ong', 'BS Hospitality Management', '2025', 'BSHM', 'College of Business and Accountancy', 'Active', '', 'Clark', '2003-02-02', 'Mother', 'Yes', 'Yes', 'Less than a month', 'Yes', 'Arranged by AUF', 'Front Office Associate', 'Clark Grand Hotel', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Guest Service, Reservations', '1412', 'Aligned', 'Approved', '', 'Front Office Briefing', 'Hospitality and food service'),
('SAMP-2018-039', 'Omar', 'Villanueva', 'Garcia', 'BS Electronics Engineering', '2018', 'BSECE', 'College of Engineering and Architecture', 'Active', '', 'Angeles City', '1996-06-18', 'Father', 'Yes', 'Yes', '3 years or more', 'Yes', 'As walk-in applicant', 'Technician', 'Clark Assembly Plant', '₱13,800 to ₱27,599', 'Contractual/Casual', 'Yes', 'No', 'Electronics Engineer', 'North Luzon Devices', '6 year(s)', 'Yes', '₱69,000 and above', '', '', 'No', '', '', '', '', 'Hardware Testing, PLC', '2152', 'Aligned', 'Claimed', '', '', 'Manufacturing'),
('SAMP-2025-040', 'Celia', 'Ramos', 'Lopez', 'BS Pharmacy', '2025', 'BSPHARM', 'College of Allied Medical Professions', 'Active', '', 'San Fernando', '2003-09-01', 'Both Parents', 'Yes', 'Yes', 'Less than a month', 'Yes', 'Public Employment Service Office / Job Fair', 'Pharmacist', 'Southwoods Pharmacy', '₱13,800 to ₱27,599', 'Probationary', 'Yes', 'Yes', '', '', '', '', '', '', '', 'No', '', '', '', '', 'Dispensing, Counseling', '2262', 'Aligned', 'ForVerification', '', '', 'Health');

  UPDATE sample_alumni
  SET email = lower(first_name) || '.' || lower(replace(last_name, ' ', '')) || '.sample@example.com';

  INSERT INTO university_records (
    student_id, first_name, middle_name, last_name, personal_email, degree, year_graduated, course_code, college
  )
  SELECT student_id, first_name, middle_name, last_name, email, degree, year_graduated, course_code, college
  FROM sample_alumni s
  WHERE NOT EXISTS (
    SELECT 1 FROM university_records u
    WHERE u.student_id = s.student_id OR u.personal_email = s.email
  );

  INSERT INTO accounts (
    personal_email, password_hash, linked_student_id, is_verified, status, role, rejection_reason,
    privacy_consent, password_changed_at, first_name, last_name, must_change_password, token_version,
    created_at, updated_at
  )
  SELECT
    s.email,
    sample_password,
    s.student_id,
    s.account_status <> 'Rejected',
    s.account_status,
    'Alumni',
    s.rejection_reason,
    true,
    now(),
    s.first_name,
    s.last_name,
    false,
    0,
    now(),
    now()
  FROM sample_alumni s
  WHERE NOT EXISTS (
    SELECT 1 FROM accounts a
    WHERE a.personal_email = s.email OR a.linked_student_id = s.student_id
  );

  INSERT INTO alumni_profiles (
    account_id, first_name, middle_name, last_name, husband_surname, country_residence, degree, year_graduated,
    guardian_type, guardian_degree_completed, job_timeline_ready, phone, city, photo_path, photo_mime,
    cover_path, cover_mime, bio, address, no_employment_reason, employment_answer_before,
    currently_unemployed, unemployment_reason, unemployment_details, birth_date, created_at, updated_at
  )
  SELECT
    a.id,
    s.first_name,
    s.middle_name,
    s.last_name,
    '',
    'Philippines',
    s.degree,
    s.year_graduated,
    s.guardian_type,
    s.guardian_degree = 'Yes',
    true,
    '+63 917 555 ' || lpad((row_number() OVER (ORDER BY s.student_id))::text, 4, '0'),
    s.city,
    '',
    '',
    '',
    '',
    'Sample CareerSense record for ' || s.degree || ', class of ' || s.year_graduated || '.',
    s.city || ', Pampanga',
    '',
    '',
    s.currently_employed = 'No',
    s.unemployment_code,
    CASE
      WHEN s.reason_current = 'Other' THEN 'Relocated and still arranging work.'
      WHEN s.unemployment_code = 'other' THEN s.reason_current
      ELSE ''
    END,
    s.birth_date,
    now(),
    now()
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE NOT EXISTS (SELECT 1 FROM alumni_profiles p WHERE p.account_id = a.id);

  INSERT INTO alumni_jobs (
    account_id, job_title, company, start_date, end_date, is_current, industry, location, salary_range, description
  )
  SELECT
    a.id,
    s.first_occ,
    s.first_emp,
    make_date(s.year_graduated::int, 8, 1),
    CASE
      WHEN s.currently_employed = 'Yes' AND s.present_is_first = 'Yes' THEN NULL
      WHEN s.present_is_first = 'No' THEN make_date(s.year_graduated::int + 2, 3, 31)
      ELSE make_date(s.year_graduated::int + 1, 12, 31)
    END,
    s.currently_employed = 'Yes' AND s.present_is_first = 'Yes',
    s.job_industry,
    s.city,
    s.first_sal,
    'First job after graduation.'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE s.ever_employed = 'Yes' AND s.first_occ <> ''
    AND NOT EXISTS (
      SELECT 1 FROM alumni_jobs j WHERE j.account_id = a.id AND j.job_title = s.first_occ
    );

  INSERT INTO alumni_jobs (
    account_id, job_title, company, start_date, end_date, is_current, industry, location, salary_range, description
  )
  SELECT
    a.id,
    s.pres_occ,
    s.pres_emp,
    make_date(s.year_graduated::int + 2, 4, 1),
    NULL,
    true,
    s.job_industry,
    s.city,
    s.pres_sal,
    'Current job.'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE s.currently_employed = 'Yes' AND s.present_is_first = 'No' AND s.pres_occ <> ''
    AND NOT EXISTS (
      SELECT 1 FROM alumni_jobs j WHERE j.account_id = a.id AND j.job_title = s.pres_occ
    );

  INSERT INTO alumni_skills (account_id, skill_name, category)
  SELECT a.id, trim(skill), 'Professional'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  CROSS JOIN LATERAL unnest(string_to_array(s.skills, ',')) AS skill
  WHERE trim(skill) <> ''
    AND NOT EXISTS (
      SELECT 1 FROM alumni_skills sk
      WHERE sk.account_id = a.id AND sk.skill_name = trim(skill)
    );

  INSERT INTO further_studies (
    account_id, course_degree, school, institution_address, year_enrolled, scholarship, is_graduated
  )
  SELECT
    a.id,
    s.study_course,
    s.study_school,
    'MacArthur Highway, Angeles City, Pampanga',
    s.study_year,
    '',
    s.study_graduated = 'Yes'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE s.enroll_further = 'Yes'
    AND NOT EXISTS (
      SELECT 1 FROM further_studies f
      WHERE f.account_id = a.id AND f.course_degree = s.study_course
    );

  INSERT INTO alumni_seminars (account_id, title, location, held_on, organizer)
  SELECT a.id, s.seminar_title, 'Angeles University Foundation', s.year_graduated || '-11-15', 'OAAPS'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE s.seminar_title <> ''
    AND NOT EXISTS (
      SELECT 1 FROM alumni_seminars sem
      WHERE sem.account_id = a.id AND sem.title = s.seminar_title
    );

  INSERT INTO alumni_awards (account_id, title, issuer, awarded_on, description)
  SELECT a.id, s.award_title, 'Angeles University Foundation', s.year_graduated || '-03-20', 'Sample recognition recorded for reports.'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE s.award_title <> ''
    AND NOT EXISTS (
      SELECT 1 FROM alumni_awards aw
      WHERE aw.account_id = a.id AND aw.title = s.award_title
    );

  INSERT INTO alumni_certifications (
    account_id, certification_name, issuing_organization, date_issued, awarded_on, skills_covered,
    is_verified, verification_url, certificate_path, certificate_mime, certificate_filename
  )
  SELECT
    a.id,
    CASE s.course_code
      WHEN 'BSA' THEN 'Certified Public Accountant Review Completion'
      WHEN 'BSN' THEN 'Basic Life Support'
      WHEN 'BSIT' THEN 'IT Specialist'
      WHEN 'BSCS' THEN 'IT Specialist'
      ELSE 'Professional Development Certificate'
    END,
    'Angeles University Foundation',
    make_date(s.year_graduated::int, 12, 1),
    s.year_graduated || '-12-01',
    '[]'::json,
    false,
    '',
    '',
    '',
    ''
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE NOT EXISTS (SELECT 1 FROM alumni_certifications c WHERE c.account_id = a.id);

  INSERT INTO tracer_submissions (
    account_id, student_id, data_json, extra_answers, alignment_status, alignment_score, soc_code, submitted_at
  )
  SELECT
    a.id,
    s.student_id,
    json_build_object(
      'first_name', s.first_name,
      'middle_name', s.middle_name,
      'last_name', s.last_name,
      'country', 'Philippines',
      'degree', s.degree,
      'year_graduated', s.year_graduated,
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
      'pres_head', CASE WHEN s.present_is_first = 'No' THEN 'Sample Supervisor' ELSE '' END,
      'pres_head_email', CASE WHEN s.present_is_first = 'No' THEN 'supervisor.sample@example.com' ELSE '' END,
      'pres_stay', s.pres_stay,
      'present_related_degree', s.present_related,
      'reason_current', CASE WHEN s.reason_current <> '' THEN json_build_array(s.reason_current) ELSE '[]'::json END,
      'reason_current_other', CASE WHEN s.reason_current = 'Other' THEN 'Relocated and still arranging work.' ELSE '' END,
      'enroll_further_studies', s.enroll_further,
      'further_studies', CASE
        WHEN s.enroll_further = 'Yes' THEN json_build_array(json_build_object(
          'course_degree', s.study_course,
          'school', s.study_school,
          'institution_address', 'MacArthur Highway, Angeles City, Pampanga',
          'year_enrolled', s.study_year,
          'scholarship', '',
          'is_graduated', s.study_graduated
        ))
        ELSE '[]'::json
      END,
      'participated_seminars', CASE WHEN s.seminar_title <> '' THEN 'Yes' ELSE 'No' END,
      'seminars_helpful', CASE WHEN s.seminar_title <> '' THEN 'Yes' ELSE '' END,
      'mentoring_rating', 4,
      'advocacy_rating', 3,
      'volunteering_rating', 3,
      'engagement_desc', 'AUF career activities helped this sample graduate prepare for work.',
      'curriculum_suggestions', json_build_object('develop_competencies', 'More practicum and industry projects'),
      'skills', COALESCE(
        (SELECT json_agg(trim(skill)) FROM unnest(string_to_array(s.skills, ',')) AS skill WHERE trim(skill) <> ''),
        '[]'::json
      ),
      'current_occupation', CASE WHEN s.present_is_first = 'No' THEN s.pres_occ ELSE s.first_occ END,
      'current_employer', CASE WHEN s.present_is_first = 'No' THEN s.pres_emp ELSE s.first_emp END
    ),
    '{}'::json,
    s.alignment,
    CASE s.alignment WHEN 'Aligned' THEN 100 WHEN 'Misaligned' THEN 0 ELSE 50 END,
    CASE
      WHEN s.soc_code <> '' AND EXISTS (SELECT 1 FROM soc_codes c WHERE c.soc_code = s.soc_code) THEN s.soc_code
      ELSE NULL
    END,
    now() - ((row_number() OVER (ORDER BY s.student_id)) || ' days')::interval
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE NOT EXISTS (SELECT 1 FROM tracer_submissions t WHERE t.account_id = a.id);

  INSERT INTO alignment_results (
    account_id, overall_match_score, alignment_justification, justification_detail, suggested_career_paths, last_updated
  )
  SELECT
    a.id,
    CASE s.alignment WHEN 'Aligned' THEN 100 WHEN 'Misaligned' THEN 0 ELSE 50 END,
    s.alignment,
    CASE s.alignment
      WHEN 'Aligned' THEN s.degree || ' matches the recorded occupation.'
      WHEN 'Misaligned' THEN 'The recorded occupation sits outside the usual path for ' || s.degree || '.'
      ELSE 'No occupation was recorded, so alignment is unknown.'
    END,
    CASE
      WHEN s.pres_occ <> '' THEN json_build_array(s.pres_occ)
      WHEN s.first_occ <> '' THEN json_build_array(s.first_occ)
      ELSE '[]'::json
    END,
    now()
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE NOT EXISTS (SELECT 1 FROM alignment_results r WHERE r.account_id = a.id);

  INSERT INTO alumni_cards (
    account_id, status, card_number, issued_at, expires_at, submitted_at, pickup_ready_at,
    pickup_location, application_json
  )
  SELECT
    a.id,
    s.card_status,
    CASE
      WHEN s.card_status IN ('ReadyForPickup', 'Claimed', 'ForRenewal') THEN 'AUF-' || replace(s.student_id, 'SAMP-', '')
      ELSE ''
    END,
    CASE WHEN s.card_status = 'Claimed' THEN now() - interval '15 days' ELSE NULL END,
    CASE WHEN s.card_status IN ('Claimed', 'ForRenewal') THEN DATE '2028-03-31' ELSE NULL END,
    CASE WHEN s.card_status <> 'NotYetApplied' THEN now() - interval '30 days' ELSE NULL END,
    CASE WHEN s.card_status IN ('ReadyForPickup', 'Claimed', 'ForRenewal') THEN now() - interval '10 days' ELSE NULL END,
    'AAPS, AUF Main Campus',
    json_build_object(
      'membership_type', 'New',
      'student_number', s.student_id,
      'email', s.email,
      'first_name', s.first_name,
      'middle_name', s.middle_name,
      'last_name', s.last_name,
      'year_graduated', s.year_graduated,
      'college', s.college,
      'course', s.degree
    )
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE NOT EXISTS (SELECT 1 FROM alumni_cards c WHERE c.account_id = a.id);

  INSERT INTO alumni_notifications (account_id, title, body, category, created_at, link)
  SELECT
    a.id,
    'Sample record is ready',
    'This CareerSense profile was loaded as sample data for reports and the alumni directory.',
    'announcement',
    now(),
    '/alumni'
  FROM sample_alumni s
  JOIN accounts a ON a.personal_email = s.email
  WHERE NOT EXISTS (
    SELECT 1 FROM alumni_notifications n
    WHERE n.account_id = a.id AND n.title = 'Sample record is ready'
  );

  IF to_regclass('public.badge_definitions') IS NOT NULL AND to_regclass('public.alumni_badges') IS NOT NULL THEN
    INSERT INTO alumni_badges (account_id, badge_key, awarded_at, award_metadata)
    SELECT a.id, b.key, now(), '{}'::json
    FROM sample_alumni s
    JOIN accounts a ON a.personal_email = s.email
    JOIN badge_definitions b ON b.key IN ('profile_complete', 'tracer_completed', 'career_updated')
    WHERE s.account_status = 'Active'
      AND NOT EXISTS (
        SELECT 1 FROM alumni_badges ab WHERE ab.account_id = a.id AND ab.badge_key = b.key
      );

    INSERT INTO alumni_badges (account_id, badge_key, awarded_at, award_metadata)
    SELECT a.id, 'alumni_card_holder', now(), '{}'::json
    FROM sample_alumni s
    JOIN accounts a ON a.personal_email = s.email
    WHERE s.card_status = 'Claimed'
      AND EXISTS (SELECT 1 FROM badge_definitions b WHERE b.key = 'alumni_card_holder')
      AND NOT EXISTS (
        SELECT 1 FROM alumni_badges ab WHERE ab.account_id = a.id AND ab.badge_key = 'alumni_card_holder'
      );
  END IF;

  SELECT count(*) INTO registry_count FROM university_records WHERE student_id LIKE 'SAMP-%';
  SELECT count(*) INTO account_count FROM accounts WHERE personal_email LIKE '%.sample@example.com';
  SELECT count(*) INTO tracer_count
  FROM tracer_submissions t
  JOIN accounts a ON a.id = t.account_id
  WHERE a.personal_email LIKE '%.sample@example.com';

  RAISE NOTICE 'Sample registry %, accounts %, tracer submissions %', registry_count, account_count, tracer_count;
END
$seed$;
