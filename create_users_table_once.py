import os
import mysql.connector

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "16042006")
DB_NAME = os.environ.get("DB_NAME", "krushibandhu_ai")

DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

def main():
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
    )
    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Ensured 'users' table exists in:", DB_NAME)

if __name__ == "__main__":
    main()
