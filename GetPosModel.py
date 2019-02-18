# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from keras.utils import to_categorical
from keras.models import Sequential
from keras.layers import LSTM, Dense
from keras.optimizers import RMSprop
import queue
import threading
import pika
import json
from loc_srv import location, tag, anchor, anchors, tags, location_record_ML
from os import listdir
import psycopg2
from time import sleep
import uuid


class GetPosModel():

	def __init__(self, data_path = "data\\", num_classes = 9, history_length = 10, nmet=1, dbparams={"user": "postgres", "passwd": "1", "host": "localhost", "port": "5432", "dbname": "postgres"}):
		self.num_classes = num_classes
		self.history_length = history_length
		self.model = Sequential()
		self.max_x = 1
		self.max_y = 1
		self.max_z = 1
		self.q_vals = queue.Queue()
		self.nmet = nmet
		self.labels = pd.Series([])
		self.killall = False
		self.conf_path = "conf_anch_zones.json"
		self.last_conf = dict()
		self.n_msrs = 1000
		
		self.conn = psycopg2.connect(user=dbparams["user"], password=dbparams["passwd"], host=dbparams["host"], port=dbparams["port"], dbname=dbparams["dbname"])
		self.cur = self.conn.cursor()
		
		self.zone_df = pd.read_sql_query("SELECT zone_id, zone_name FROM zones", self.conn)
		self.tag_df = pd.read_sql_query("SELECT tag_id, tag_name FROM tags", self.conn)
		
		connection = pika.BlockingConnection(pika.ConnectionParameters('192.168.4.101', credentials = pika.PlainCredentials('User1', 'user1')))

		#connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
		channel = connection.channel()

		channel.queue_declare(queue='locations_ML')

		def get_data():	
			n_rm = len(self.zone_df.index)
			df = pd.DataFrame(columns=["x", "y", "z", "label"])
			diff1 = pd.Series([])
			diff2 = pd.Series([])
			diff3 = pd.Series([])
			
			for idx in self.zone_df.index:
				curr_name = str(self.zone_df.loc[idx, "zone_name"])
				input("Положите метку на РМ: %s. Нажмите Enter..." % (curr_name))
				print("Собираю данные...")
				messages = 0
				
				def callback(ch, method, properties, body):
					
					nonlocal messages, diff1, diff2, diff3, curr_name
					
					#print ("Received %r" % (body,))
					data = json.loads(body)
					#print (data)
					l = location_record_ML(data['id'], data['name'], pd.Timestamp.now(), location(data['last_pos']['x'], data['last_pos']['y'], data['last_pos']['z']), data['diff1'], data['diff2'], data['diff3'])
					
					self.labels = self.labels.append(curr_name)
					#lb_name = labels[len(labels) - 1]
					diff1 = diff1.append(l.diff1)
					diff2 = diff2.append(l.diff2)
					diff3 = diff3.append(l.diff3)
					
					messages += 1
					if messages >= 1000:
						ch.stop_consuming()
					

				channel.basic_consume(callback,
									queue='locations_ML',
									no_ack=True)
				channel.start_consuming()
		
			df.loc[:,"x"] = diff1
			df.loc[:,"y"] = diff2
			df.loc[:,"z"] = diff3
			df.loc[:,"label"] = self.labels

			self.df_in = df
			self.df_in.to_excel("df_in.xlsx")
		
		try:
			read_conf()
			if conf_changed():
				collect_data()
			else:
				self.df_in = pd.read_excel("df_in.xlsx")
				self.labels = self.df_in["label"]
		except:
			get_data()
			write_conf()
			
		self.labels = self.labels.drop_duplicates().reset_index(drop=True)
	
	def read_conf(self):
		f = open(self.conf_path, "r")
		self.last_conf = json.load(f)
		f.close()
	
	def write_conf(self):
		f = open(self.conf_path, "w")
		json.dump(self.last_conf, f)
		f.close()
	
	def get_conf(self):
		zones = pd.read_sql_query("SELECT zone_id, zone_name,  FROM zones", self.conn) # FILTER TO GET RabMest
		# GETTING ANCHORS
		
		return {"zones": zones,
				"anchors": "no anchors"}
				
	def conf_changed(self):
		if self.last_conf["zones"].equals(self.get_conf()["zones"]):
			# CHECK ANCHORS
			#if :
			return False
			#pass
		return True
		
	def getDataset(self):
		def make_dataset(data, history_length):
			n = data.shape[0] - history_length
			
			lbls = dict((self.labels[self.labels.index[i]], i) for i in range(len(self.labels)))
			#print(lbls)
			#input()
			X_train = np.zeros((n, history_length, 3))
			Y_train = np.zeros(n)

			for i in range(n):
				X_train[i, :, 0] = data["x"][(0 + i):(history_length + i)]
				X_train[i, :, 1] = data["y"][(0 + i):(history_length + i)]
				X_train[i, :, 2] = data["z"][(0 + i):(history_length + i)]
			
				Y_train[i] = lbls[data["label"][data.index[0]]]
    
			#X_train1 = np.concatenate((X_train_x, X_train_y, X_train_z), axis=1)
			#Y_train1 = np.concatenate((Y_train_x, Y_train_y, Y_train_z), axis=1)
    
			return X_train, Y_train

		X = []
		Y = []
		for sym in self.labels:
			data = self.df_in[:][self.df_in["label"] == sym]
			#x, y = make_dataset(data.loc[data.index[:int(len(data.index) * 0.75)]], 20)
			x, y = make_dataset(data, self.history_length)
			X.extend(x)
			Y.extend(y)

		X = np.asarray(X)
		Y = np.asarray(Y)

		max_price_x = np.abs(X[:, :, 0]).max()
		max_price_y = np.abs(X[:, :, 1]).max()
		max_price_z = np.abs(X[:, :, 2]).max()
    
		X[:, :, 0] = X[:, :, 0] / max_price_x
		X[:, :, 1] = X[:, :, 1] / max_price_y
		X[:, :, 2] = X[:, :, 2] / max_price_z

		Y = to_categorical(y=Y, num_classes=self.num_classes)
		
		return X, Y
	
	def buildModel(self):
		self.model.add(LSTM(128, return_sequences=True, dropout=0.2, recurrent_dropout=0.2, input_shape=(self.history_length, 3,)))
		self.model.add(LSTM(64, return_sequences=True, dropout=0.2, recurrent_dropout=0.2))
		self.model.add(LSTM(32, dropout=0.2, recurrent_dropout=0.2))
		#self.model.add(Dense(100, activation='relu'))
		self.model.add(Dense(self.num_classes, activation='softmax'))
		self.model.compile(loss='mae', optimizer=RMSprop(), metrics=['acc'])
		#self.model._make_predict_function()
		print(self.model.summary())

	def initWeights(self, weights_path):
		self.model.load_weights(weights_path)
		
	def train(self, X, Y, weights_path, epochs, batch_size):
		self.model.fit(X, Y, epochs=epochs, batch_size=batch_size)
		self.model.save_weights(filepath=weights_path)
	
	def countNormCoeffs(self):
		self.max_x = np.abs(self.df_in["x"]).max()
		self.max_y = np.abs(self.df_in["y"]).max()
		self.max_z = np.abs(self.df_in["z"]).max()
		
	def check(self, X):
		for k in X:
			if len(X[k]) < self.history_length:
				return False

		return True	
		
	def work(self):
		
		#engine = create_engine("postgresql+pypostgresql://postgres:1@localhost:5432/postgres")

		#conn = engine.connect()
		#conn.begin()
	
		connection = pika.BlockingConnection(pika.ConnectionParameters('192.168.4.101', credentials = pika.PlainCredentials('User1', 'user1')))

		#connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
		channel = connection.channel()

		channel.queue_declare(queue='locations_ML')
		
		self.q_vals = dict((self.tag_df["tag_name"][self.tag_df.index[idx]], queue.Queue()) for idx in range(len(self.tag_df.index)))
		self.forpred = queue.Queue()
		#print(self.q_vals)
		print ('Waiting for messages...')
		
		def callback(ch, method, properties, body):
			#print ("Received %r" % (body,))
			data = json.loads(body)
			#print (data)
			l = location_record_ML(data['id'], data['name'], pd.Timestamp.now(), location(data['last_pos']['x'], data['last_pos']['y'], data['last_pos']['z']), data['diff1'], data['diff2'], data['diff3'])
			#print("%s %s %s" % (l.name, l.diff1, l.diff2))
			#l = location_record(data['id'])
			#print ("x=%s y=%s " % (l.last_pos.x, l.last_pos.y))
			#print(l.name)
			self.q_vals[l.name].put(l)

		channel.basic_consume(callback,
							queue='locations_ML',
							no_ack=True)
		t = threading.Thread(target=channel.start_consuming)
		#t = threading.Thread(target=tmp_foo)
		t.start()
		
		idx2lbls = dict((i, self.labels[self.labels.index[i]]) for i in range(len(self.labels.index)))
		#X = dict(("Sim_Tag_" + str(k), []) for k in range(self.nmet))
		#while not self.check(X):
		def proc_mes(que):
			X = []
			name = ""
			datetime = ""
			for _ in range(self.history_length):
				item = que.get()
				name = item.name
				#X["met0"].append([item.diff1 / self.max_x, item.diff2 / self.max_y, item.diff3 / self.max_z])
				#X[X.keys[item.name]].append([float(item.diff1) / self.max_x, float(item.diff2) / self.max_y, float(item.diff3) / self.max_z])
				X.append([float(item.diff1) / self.max_x, float(item.diff2) / self.max_y, float(item.diff3) / self.max_z])
				datetime = item.datetime
			self.forpred.put({"name": name, "data": np.asarray([X]), "time": datetime})
			
			while not self.killall:
				item = que.get()
				#X["met0"].append([item.diff1 / self.max_x, item.diff2 / self.max_y, item.diff3 / self.max_z])
				X.append([float(item.diff1) / self.max_x, float(item.diff2) / self.max_y, float(item.diff3) / self.max_z])
				#y = np.argmax(self.model.predict(np.asarray([np.roll(np.asarray(X["met0"]), -1)[:self.history_length]])))
				self.forpred.put({"name": item.name, "data": np.asarray([X[len(X) - self.history_length:]]), "time": item.datetime})
				
			#conn.close()
		tmp_ques = [self.q_vals[self.tag_df["tag_name"][self.tag_df.index[idx]]] for idx in range(len(self.tag_df.index))]
		tds = []
		for i in range(len(tmp_ques)):
			tds.append(threading.Thread(target=lambda: proc_mes(tmp_ques[i])))
		for i in range(len(tmp_ques)):
			tds[i].start()
		
		def cmmt_pg():
			while not self.killall:
				self.conn.commit()
				sleep(1)
		
		commit_thread = threading.Thread(target=cmmt_pg)
		commit_thread.start()
		
		tgznd_req = "INSERT INTO tag_zone_drafts (tgznd_id, tgznd_tag_id, tgznd_zone_id, tgznd_date, tgznd_duration) VALUES (%s, %s, %s, %s, %s)"
		try:
			while True:
				a = self.forpred.get()
				tmp = self.model.predict(a["data"])
				y = np.argmax(tmp)
				#print(name)
				#sql.execute('INSERT INTO \"tag_zone_drafts\" (\"tgznd_tag_id\", \"tgznd_zone_id\", \"tgznd_date\", \"tgznd_duration\") VALUES (?, ?, ?, ?)', engine,
				#    params=[("4321", str(y), pd.Timestamp.now(), 112)])
				
				print(a["name"] + ": " + idx2lbls[y])
				tgid = self.tag_df["tag_id"][self.tag_df["tag_name"] == a["name"]].values[0]
				znid = self.zone_df["zone_id"][self.zone_df["zone_name"] == idx2lbls[y]].values[0]
				self.cur.execute(tgznd_req, (str(uuid.uuid4()), tgid, znid, a["time"], pd.Timedelta(100, "ms")))
		except KeyboardInterrupt:
			self.killall = True
		#t = threading.Thread(target=channel.start_consuming)
		#t = threading.Thread(target=tmp_foo)
		#t.start()
		
		
if __name__ == "__main__":
	#path = "Y:\\workdir\\get_position\\"
	getpos = GetPosModel(data_path="data\\", num_classes=9, history_length=10, nmet=2)
	#X, Y = getpos.getDataset()
	getpos.buildModel()
	#getpos.train(X, Y, "test_lstm_diff_pos.weights", 200, 64)
	
	getpos.initWeights("test_lstm_diff_pos.weights")
	getpos.countNormCoeffs()
	getpos.work()
	
	getpos.cur.close()
	getpos.conn.close()