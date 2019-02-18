import pika
import json
from loc_srv import location, tag, anchor, anchors, tags, location_record_ML
import pandas as pd

import pika
from time import sleep
from random import randint, random

#import psycopg2

#conn = psycopg2.connect(user='postgres', password='1', host='localhost', port='5432', dbname='postgres')
#tag_df = pd.read_sql_query("SELECT tag_id, tag_name FROM tags", conn)

metkas = {"123231432": "Egor1"}


connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
ch2 = connection.channel()

channel.queue_declare(queue='locations_ML')
ch2.queue_declare(queue='messages')
#l_ML = location_record_ML(rec.tag_id, tag_list.get_tag_by_id(rec.tag_id).name, today, location(pos_x, pos_y, pos_z), t2, t3, t4)
#l = location_record_ML('id', 'name', pd.Timestamp.now(), location(1.223, 3.211, 0.654), 13.12, 51.43, 43.1121)

while True:
	#idx = tag_df.index[randint(0,2)]
	l = location_record_ML("123213123", "Egor1", pd.Timestamp.now(), location(3.122, 3.211, 0.654), random() * 340 - 170, random() * 340 - 170, random() * 340 - 170)
	print("%s %f %f" % (l.name, l.diff1, l.diff2))
	channel.basic_publish(exchange='',
                      routing_key='locations_ML',
                      body=l.get_json())
	ch2.basic_publish(exchange='', routing_key='messages', body=l.get_json())
	#sleep(0.1)

#print(" [x] Sent 'Hello World!'")