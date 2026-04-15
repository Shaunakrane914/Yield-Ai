from dotenv import load_dotenv
import os
import mysql.connector
import psycopg2

load_dotenv()

m = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME", "krushibandhu_ai"),
)
p = psycopg2.connect(os.getenv("SUPABASE_DB_URL"))

mc = m.cursor()
pc = p.cursor()

mc.execute("SHOW TABLES")
tables = [r[0] for r in mc.fetchall()]

mismatches = []
print("TABLE,MYSQL,POSTGRES")
for t in tables:
    mc.execute(f"SELECT COUNT(*) FROM `{t}`")
    mcnt = mc.fetchone()[0]
    pc.execute(f'SELECT COUNT(*) FROM "{t}"')
    pcnt = pc.fetchone()[0]
    print(f"{t},{mcnt},{pcnt}")
    if mcnt != pcnt:
        mismatches.append(t)

print(f"MISMATCH_COUNT,{len(mismatches)}")
print("MISMATCH_TABLES," + ", ".join(mismatches))

mc.close()
pc.close()
m.close()
p.close()
