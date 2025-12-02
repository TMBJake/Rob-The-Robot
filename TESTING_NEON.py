import psycopg2
from datetime import datetime

# ? FILL THESE WITH YOUR REAL NEON VALUES ?
NEON_DBNAME = "neondb"            # or your DB name
NEON_USER = "neondb_owner"
NEON_PASSWORD = "npg_NKCar8DIJ3Gf"
NEON_HOST = "ep-sweet-night-a4uii4iq-pooler.us-east-1.aws.neon.tech"
NEON_PORT = 5432

def test_insert():
    try:
        conn = psycopg2.connect(
            dbname=NEON_DBNAME,
            user=NEON_USER,
            password=NEON_PASSWORD,
            host=NEON_HOST,
            port=NEON_PORT,
            sslmode="require",   # Neon usually requires SSL
        )
        cur = conn.cursor()

        now = datetime.utcnow().isoformat()
        distance = 42.0
        line_side = "middle"
        voltage = 7.2

        cur.execute("""
            INSERT INTO sensor_data (timestamp, distance, line_side, voltage)
            VALUES (%s, %s, %s, %s)
        """, (now, distance, line_side, voltage))

        conn.commit()
        cur.close()
        conn.close()

        print("? Inserted test row into Neon successfully")

    except Exception as e:
        print("? Failed to insert into Neon:")
        print(e)

if __name__ == "__main__":
    test_insert()
