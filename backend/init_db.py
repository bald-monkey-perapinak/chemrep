import psycopg2
c = psycopg2.connect(host='localhost', port=5432, user='postgres', dbname='postgres')
c.autocommit = True
cur = c.cursor()
cur.execute("SELECT datname FROM pg_database WHERE datname='chemrep'")
if not cur.fetchone():
    cur.execute('CREATE DATABASE chemrep')
    print('Database chemrep created')
else:
    print('Database chemrep exists')
c.close()
