"""Reset password for hkala8639@gmail.com to '12345678'"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="ai_interviewer",
    user="postgres",
    password="62635494",
)
cur = conn.cursor()

# Show current users
cur.execute("SELECT id, email, is_active FROM users;")
rows = cur.fetchall()
print("Current users:")
for row in rows:
    print(f"  id={row[0]}, email={row[1]}, active={row[2]}")

# Update password
new_hash = "$2b$12$9KDkCq5XLTjZXak16ZSXgu72R.Rfpd9XpWAEciXrEcb9y1oye8gVK"
cur.execute(
    "UPDATE users SET hashed_password=%s WHERE email=%s RETURNING id, email;",
    (new_hash, "hkala8639@gmail.com"),
)
updated = cur.fetchall()
conn.commit()

if updated:
    print(f"\n✅ Password reset for: {updated[0][1]}")
    print("   New password: 12345678")
else:
    print("\n⚠️  User hkala8639@gmail.com not found — registering via API instead")

cur.close()
conn.close()

