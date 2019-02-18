import GetPosModel as gpm
import argparse
import json
import os

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--num_classes', type=int,
                    help='количество рабочих мест')
parser.add_argument('-m', '--nmet', type=int, help='количество меток')
args = parser.parse_args()

with open('pg_conf.json', "r") as json_file:  
    dbparams = json.load(json_file)
try:
	os.remove("df_in.xlsx")
except:
	pass
getpos = gpm.GetPosModel(data_path="data\\", num_classes=args.num_classes, history_length=10, nmet=args.nmet, dbparams=dbparams)
X, Y = getpos.getDataset()
getpos.buildModel()
getpos.train(X, Y, "lstm_diff_pos.weights", 150, 64)

getpos.work()