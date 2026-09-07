import psycopg2, os
from dotenv import load_dotenv
load_dotenv('c:/Users/neeha/OneDrive/Desktop/Work/Form20_Dashboard_Release/.env')
conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ['DB_PORT'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], dbname=os.environ['DB_NAME'])
cur = conn.cursor()
cur.execute("SELECT el_year, el_type, COUNT(DISTINCT ac_no) FROM ac_election_mapping WHERE state_abb='AR' GROUP BY el_year, el_type")
rows = cur.fetchall()
print('AR Expected Elections:', len(rows))
for r in rows:
    print(r)
