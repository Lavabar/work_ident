import psycopg2
import pandas as pd
import uuid
#import datetime

#origin_time = '1972-01-01 00:00:00'
#d = datetime.datetime.strptime(origin_time, '%Y-%m-%d %H:%M:%S')

#a = pd.Timedelta(1, "s")
#input(a)

conn = psycopg2.connect(user='postgres', password='1', host='localhost', port='5432', dbname='postgres')
cur = conn.cursor()

zones = [str(uuid.uuid4()) for _ in range(9)]
zone_names = ["Zone" + str(i) for i in range(9)]
tag_ids = [str(uuid.uuid4()) for _ in range(1)]
tag_names = ["Tag_" + str(i) for i in range(1)]

zones_req = "INSERT INTO zones (zone_id, zone_name) VALUES (%s, %s)"
for i in range(len(zones)):
	cur.execute(zones_req, (zones[i], zone_names[i]))
	
tags_req = "INSERT INTO tags (tag_id, tag_name) VALUES (%s, %s)"
for i in range(len(tag_ids)):
	cur.execute(tags_req, (tag_ids[i], tag_names[i]))

#tgznd_req = "INSERT INTO tag_zone_drafts (tgznd_id, tgznd_tag_id, tgznd_zone_id, tgznd_date, tgznd_duration) VALUES (%s, %s, %s, %s, %s)"
#cur.execute(tgznd_req, (, str(uuid.uuid1()), str(uuid.uuid1()), pd.Timestamp.now(), pd.Timedelta(1, "s")))

conn.commit()

cur.close()
conn.close()