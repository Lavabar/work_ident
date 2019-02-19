import pandas as pd
import numpy as np

import queue
import pika
import json
from loc_srv import location, tag, anchor, anchors, tags, location_record_ML
from os import listdir

#connection = pika.BlockingConnection(pika.ConnectionParameters('192.168.38.215', credentials = pika.PlainCredentials('User1', 'user1')))

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='messages')

def callback(ch, method, properties, body):
	print ("Received %r" % (body,))
	f.write(str(body) + "\n")

for person_id in range(2):
    input("Press \"Enter\" if ready")
    f = open("person{}.txt".format(person_id), "w")
    print ('Waiting for messages...')
	
    channel.basic_consume(callback,
					queue='messages',
					no_ack=True)

    try:				
	    channel.start_consuming()
    except KeyboardInterrupt:
	    pass
    f.close()

