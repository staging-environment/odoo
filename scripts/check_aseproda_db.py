import pymysql
import json

conn = pymysql.connect(host='10.8.0.6', port=3306, user='root', password='.root.', charset='utf8', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SHOW TABLES FROM virtusgesnet WHERE `Tables_in_virtusgesnet` LIKE '%config%' OR `Tables_in_virtusgesnet` LIKE '%pista%' OR `Tables_in_virtusgesnet` LIKE '%sdes%'")
    tables = [list(r.values())[0] for r in cur.fetchall()]
    print("Tables:", tables)

    for t in tables:
        cur.execute(f"SELECT * FROM virtusgesnet.{t} LIMIT 10")
        print(f"\n--- {t} ---")
        print(json.dumps(cur.fetchall(), indent=2, default=str))

conn.close()
