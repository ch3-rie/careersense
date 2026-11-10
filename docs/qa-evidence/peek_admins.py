import sqlite3

c = sqlite3.connect(r"backend/careersense.db")
for row in c.execute("select id, personal_email, employee_number, admin_privileges, status from accounts where role='Admin'"):
    print(row)
