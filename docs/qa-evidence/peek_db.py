import sqlite3

c = sqlite3.connect(r"backend/careersense.db")
print("TABLES")
for row in c.execute("select name from sqlite_master where type='table' order by name"):
    print(row[0])
print("COLUMNS", [r[1] for r in c.execute("pragma table_info(university_records)")])
print("UNUSED")
for row in c.execute(
    """
    select u.student_id, u.first_name, u.last_name, u.personal_email, u.degree, u.year_graduated
    from university_records u
    where u.student_id not in (select linked_student_id from accounts where linked_student_id is not null)
    limit 12
    """
):
    print(row)
print("ACCOUNTS")
for row in c.execute(
    "select id, personal_email, role, status from accounts where personal_email like '%navarro%' or personal_email like '%lim%' or personal_email like '%mendoza%' or personal_email like '%santos%' or personal_email like 'qa.%'"
):
    print(row)
