import psycopg2, os
from dotenv import load_dotenv
load_dotenv('c:/Users/neeha/OneDrive/Desktop/Work/Form20_Dashboard_Release/.env')
conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ['DB_PORT'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], dbname=os.environ['DB_NAME'])
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM ac_election_mapping WHERE state_abb='CG'")
print('CG mapping:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM ac_election_mapping WHERE state_abb='CT'")
print('CT mapping:', cur.fetchone()[0])
