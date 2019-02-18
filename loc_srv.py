import sys
import serial 
import struct
from colorama import init
import csv
import time
import datetime
import threading
import queue
#import msvcrt # windows only
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.path import Path
import matplotlib.patches as patches
import atexit
import pika
import json
import math

waiting_cmd_confirm = int()

#TODO исправить x y z в якорях на location
#TODO переименовать класс record


class location:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

class location_record:
    def __init__(self, id, name = '', today = '', last_pos = location(0,0,0), aver_pos = location(0,0,0), zone = '', tag_type = '', algorithm = 'TDoA', color = 'black', shape = 'cone', misc = ''):
        self.id = id
        self.name = name
        self.date = today.strftime("%Y:%m:%d")
        self.time = today.strftime("%H:%M:%S")
        self.datetime = today.strftime("%Y.%m.%d %H:%M:%S")
        self.last_pos = last_pos
        self.aver_pos = aver_pos
        self.zone = zone
        self.tag_type = tag_type
        self.algorithm = algorithm
        self.color = color
        self.shape = shape
        self.misc = misc

    def get_json(self):
        arr = '{'
        pos = 0
        for param_name, param_value in self.__dict__.items():
            if param_name == 'last_pos' or param_name == 'aver_pos':
                arr += '"' + param_name + '": {'
                pos_sub = 0
                for sub_param_name, sub_param_value in param_value.__dict__.items():
                    arr += ('"{0}": "{1}"'.format(sub_param_name, sub_param_value))
                    if pos_sub < (len(param_value.__dict__) - 1):
                        arr += ','
                    pos_sub += 1
                arr += '}'
            else:
                arr += '"{0}": "{1}"'.format(param_name, param_value)
            if pos < (len(self.__dict__) - 1):
                arr += ','
            pos += 1
        arr += '}'

        json_txt = json.dumps(arr)
        json_txt = (json_txt.replace("}, {","}\\\0{")).replace("\\","")
        json_txt = (json_txt.replace("\"[","")).replace("]\"","") + chr(0)
        json_txt = json_txt[1:(len(json_txt)-2)] 
        return json_txt

class location_record_ML:
    def __init__(self, id, name = '', today = '', last_pos = location(0,0,0), diff1 = 0, diff2 = 0, diff3 = 0):
        self.id = id
        self.name = name
        self.datetime = today.strftime("%Y.%m.%d %H:%M:%S")
        self.last_pos = last_pos
        self.diff1 = diff1
        self.diff2 = diff2
        self.diff3 = diff3

    def get_json(self):
        arr = '{'
        pos = 0
        for param_name, param_value in self.__dict__.items():
            if param_name == 'last_pos' or param_name == 'aver_pos':
                arr += '"' + param_name + '": {'
                pos_sub = 0
                for sub_param_name, sub_param_value in param_value.__dict__.items():
                    arr += ('"{0}": "{1}"'.format(sub_param_name, sub_param_value))
                    if pos_sub < (len(param_value.__dict__) - 1):
                        arr += ','
                    pos_sub += 1
                arr += '}'
            else:
                arr += '"{0}": "{1}"'.format(param_name, param_value)
            if pos < (len(self.__dict__) - 1):
                arr += ','
            pos += 1
        arr += '}'

        json_txt = json.dumps(arr)
        json_txt = (json_txt.replace("}, {","}\\\0{")).replace("\\","")
        json_txt = (json_txt.replace("\"[","")).replace("]\"","") + chr(0)
        json_txt = json_txt[1:(len(json_txt)-2)] 
        return json_txt

class tag:
    # last_pos = location(0, 0, 0)
    # aver_pos = location(0, 0, 0)

    def __init__(self, name, id, color = 'black'):
        self.name = name
        self.id = id
        self.color = color
        self.startup = 0
        self.aver_pos = location(0,0,0)
        self.last_pos = location(0,0,0)

class anchor:
    def __init__(self, name, id, x, y, z, sync_master = False, sync_level = 0):
        self.name = name
        self.id = id
        self.x = x
        self.y = y
        self.z = z

class anchors:
    __anchor_list = []

    def __init__(self):
        self.name = ''

    def add_anchor(self, new_anchor):
        if len(self.__anchor_list) == 0:
            self.__anchor_list.append(new_anchor)
        else:
            if self.__anchor_list.count(new_anchor) == 0:
                self.__anchor_list.append(new_anchor)   

    def get_anchor_by_id (self, anchor_id):
        for an in self.__anchor_list:
            if an.id == anchor_id:
                return an

    def get_anchor_by_index(self, index):
        if index >= len(self.__anchor_list):
            return None
        try:
            return self.__anchor_list[index]
        except ValueError:
            return None       

    def get_anchor_by_name(self, anchor_name):
        for i in self.__anchor_list:
            if i.name == anchor_name:
                return i
        return None

    def len(self):
        return len(self.__anchor_list)        

    def get_anchors(self):
        return self.__anchor_list

class record:
    def __init__(self, dest_id, src_id, blink_type, tag_id, timestamp, blink_id, param_id, param_value):
        self.dest_id = dest_id
        self.src_id = src_id
        self.blink_type = blink_type
        self.tag_id = tag_id
        self.timestamp = timestamp
        self.blink_id = blink_id
        self.param_id = param_id
        self.param_value = param_value
        self.age = 0


class tags:
    __tag_list = [] # Список id видимых меток (пока без удаления)
    __tag_records = [] # Временный список для хранения необработанных записей от якорей
    __tags = [] # Список меток
    
    def __init__(self):
        self.name = ''

    def get_tag_by_id(self, tag_id): # Возвращает метку по ее id номеру
        for t in self.__tags:
            if int(t.id) == int(tag_id):
                return t
        return None

    def add_tag(self, new_tag): #  Добавляет метку в список с предварительной проверкой на дубль  
        if self.get_tag_by_id(new_tag.id) != None:
            return
        else: 
            self.__tags.append(new_tag)
        

    def add_record(self, new_rec): # При добавлении строки проверяем tad_id 
        if len(self.__tag_list) == 0:
            self.__tag_list.append(new_rec.tag_id)
            self.add_tag(tag(name ='', id = new_rec.tag_id))
        else:
            if self.__tag_list.count(new_rec.tag_id) == 0:
                self.__tag_list.append(new_rec.tag_id)
                self.add_tag(tag(name ='', id = new_rec.tag_id))
        # Добавляем запись без обработки, она будет обработана потом, при вызове get_location 
        self.__tag_records.append(new_rec)


    def calc_location_TDOA(self, anchor_list, tag_list, tag_list_for_location_engine):
        if len(tag_list_for_location_engine) < 4:
            print_debug_1(bcolors.yellow + 'мало данных' + bcolors.reset)
            return None
        
        print_debug_1(bcolors.green + 'TDoA calc func. Tag Name: ' + str((tag_list.get_tag_by_id(tag_list_for_location_engine[0].tag_id)).name) + '  id: ' + str(tag_list_for_location_engine[0].tag_id) + '  blink no: ' + str(tag_list_for_location_engine[0].blink_id) + '     Кол-во записей ' + str(len(tag_list_for_location_engine)) + bcolors.reset)
        
        for r in tag_list_for_location_engine:
            print_debug_1(bcolors.green + '\tAnchor Name: ' + str(anchor_list.get_anchor_by_id(r.src_id).name) + '\tid: ' + str(r.src_id) + '\tTimestamp: ' + str(r.timestamp) + bcolors.reset)
        
        
        
        anchor_time = []
        for an in tag_list_for_location_engine:
            anchor_time.append(an.timestamp)

        # Координаты якорей
        x1 = float(anchor_list.get_anchor_by_id(tag_list_for_location_engine[0].src_id).x) 
        y1 = float(anchor_list.get_anchor_by_id(tag_list_for_location_engine[0].src_id).y) 

        x2 = float(anchor_list.get_anchor_by_id(tag_list_for_location_engine[1].src_id).x) 
        y2 = float(anchor_list.get_anchor_by_id(tag_list_for_location_engine[1].src_id).y) 

        x3 = float(anchor_list.get_anchor_by_id(tag_list_for_location_engine[2].src_id).x) 
        y3 = float(anchor_list.get_anchor_by_id(tag_list_for_location_engine[2].src_id).y) 

        x4 = float(anchor_list.get_anchor_by_id(tag_list_for_location_engine[3].src_id).x) 
        y4 = float(anchor_list.get_anchor_by_id(tag_list_for_location_engine[3].src_id).y) 

        # Проверка времени с момента синхронизации 
        #if tag_list_for_location_engine[0].timestamp > 150000:
        #    return None

        # Разница во времени приема сигнала от метки
        t2 = convert_DW_time_to_s(tag_list_for_location_engine[1].timestamp - tag_list_for_location_engine[0].timestamp)
        t3 = convert_DW_time_to_s(tag_list_for_location_engine[2].timestamp - tag_list_for_location_engine[0].timestamp)
        t4 = convert_DW_time_to_s(tag_list_for_location_engine[3].timestamp - tag_list_for_location_engine[0].timestamp)

        # Проверка разницы во времени между якорями, она не должна превышать расстояния 56м (диагональ 40х40) не более 200 нс
        max_td = 0
        for r1 in tag_list_for_location_engine:
            for r2 in tag_list_for_location_engine:
                max_td = abs(r1.timestamp - r2.timestamp) if abs(r1.timestamp - r2.timestamp) > max_td else max_td
        if max_td > 200:
            print_debug_1(bcolors.yellow + 'большая разница во времени' + bcolors.reset)
            return None

        # Вычисление координат метки
        # Скорость света в воздухе
        v = 299704000.0

        A1 = (-2.0)*(t2*(x1 - x3) - t3*(x1 - x2))
        A2 = (-2.0)*(t2*(x1 - x4) - t4*(x1 - x2))

        B1 = (-2.0)*(t2*(y1 - y3) - t3*(y1 - y2))
        B2 = (-2.0)*(t2*(y1 - y4) - t4*(y1 - y2))

        C1 = t2*(x1**2 - x3**2 + y1**2 - y3**2) - t3*(x1**2 - x2**2 + y1**2 - y2**2) - v**2*(t2 - t3)*t2*t3
        C2 = t2*(x1**2 - x4**2 + y1**2 - y4**2) - t4*(x1**2 - x2**2 + y1**2 - y2**2) - v**2*(t2 - t4)*t2*t4



        # Проверка на возможность решения
        if (B2 == 0):
            print_debug_1(bcolors.yellow + 'нет решения B2 = 0' + bcolors.reset)
            return None   
        if ((A1 - A2*B1/B2) == 0):
            print_debug_1(bcolors.yellow + 'нет решения A1 = A2*B1/B2' + bcolors.reset)
            return None
        
        # Вычисление координат метки
        pos_x = (B1 * C2/B2 - C1)/(A1 - A2*B1/B2)
        pos_y = (-(A2 * pos_x + C2)/B2)
        pos_z = 0

        if self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).startup == 0: 
            Kl = 1
            self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).startup += 1
        elif (self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).startup > 0) and (self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).startup < 10): 
            Kl = 0.75
            self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).startup += 1
        else:
            Kl = setup.filter_K
            # Проверка расстояния от предыдущей позиции, если более 10м, то возможно это неправильный результат
            if dist(location(pos_x, pos_y, pos_z), self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).aver_pos) > 10:
                Kl = 0

        aver_pos_x = (1 - Kl) * self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).aver_pos.x + Kl * pos_x
        aver_pos_y = (1 - Kl) * self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).aver_pos.y + Kl * pos_y
        aver_pos_z = (1 - Kl) * self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).aver_pos.z + Kl * pos_z

        self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).last_pos = location(pos_x, pos_x, pos_z)
        self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).aver_pos = location(aver_pos_x, aver_pos_y, aver_pos_z)

        # Запись строки в файл только для корректных данных
        if setup.record == True:
            row_list = {'time':time.strftime("%H%M%S"), 'tag_id': str(tag_list_for_location_engine[0].tag_id), 'tag_name': str(self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).name),'blink_id': str(tag_list_for_location_engine[0].blink_id)}
            for a in anchor_list.get_anchors():
                # Перебираем последовательно все якоря и если данные от якоря есть в списке, то пишем значение, в противном случае пусто
                for i in range(len(tag_list_for_location_engine)):
                    if a.id == anchor_list.get_anchor_by_id(tag_list_for_location_engine[i].src_id).id:
                        t = tag_list_for_location_engine[i].timestamp
                        row_list.update({a.name: str(t)})
            row_list.update({'last_pos_x':pos_x, 'last_pos_y':pos_y, 'last_pos_z':pos_z, 'aver_pos_x':aver_pos_x, 'aver_pos_y':aver_pos_y, 'aver_pos_z':aver_pos_z}) 
            writer.writerow(row_list)

        if setup.rabbitmq == True:
            today = datetime.datetime.today()
            l_ML = location_record_ML(rec.tag_id, tag_list.get_tag_by_id(rec.tag_id).name, today, location(pos_x, pos_y, pos_z), t2, t3, t4)
            msg_txt_ML = l_ML.get_json()
            channel.basic_publish(exchange = '', routing_key = 'locations_ML', body = msg_txt_ML)        

        if setup.filter == True:
            if self.get_tag_by_id(tag_list_for_location_engine[0].tag_id).startup < 10: 
                return None
            return location(aver_pos_x, aver_pos_y, aver_pos_z)
        else:
            return location(pos_x, pos_y, pos_z)

    def calc_location(self, anchor_list):
        ''' 
        Функция поиска решений среди частного списка записей __tag_records
        Вызывать с приходом каждой строки данных не нужно
        Алгоритм производит перебор по всем данным, последовательно фильтруя их по номеру метки, затем по номеру блинка и если
        находится комбинация из 4-х строк c одинаковыми id, номером блинка и при условии что возраст не более заданного значения,
        передает набор значений в функцию вычисления координат метки
        '''
        for t1 in self.__tag_list: # Перебор всех зарегистрированных меток
            # Фильтрация списка по номеру метки 
            records_list_filtered_by_tag_id = list(filter(lambda x: x.tag_id == t1, self.__tag_records))

            # Если отфильтрованный список нулевой длины, переход к следующему
            if len(records_list_filtered_by_tag_id) == 0:
                continue
            
            # Построение списка блинков для данного набора
            tag_blinks = []
            for r in records_list_filtered_by_tag_id:
                tmp_blink_id = r.blink_id
                if tmp_blink_id not in tag_blinks:
                    tag_blinks.append(tmp_blink_id)

            for blink in tag_blinks:      
                # Фильтруем промежуточный список по каждому блинку в списке блинков
                tag_list_for_location_engine = list(filter(lambda x: (x.blink_id == blink) and (x.age < 99), records_list_filtered_by_tag_id))
                
                # Сортируем список по полю src_id (id якоря) 
                tag_list_for_location_engine.sort(key=lambda r: r.src_id, reverse=False)

                # если в списке 4 значения или более, то предаем его в калькуляцию
                if len(tag_list_for_location_engine) > 3:
                    rez = self.calc_location_TDOA(anchor_list, tag_list, tag_list_for_location_engine)
                    
                    # TODO добавить внесение записи в список записей или БД

                    if rez != None:
                        print(bcolors.yellow + '\tTag Name: ' + tag_list.get_tag_by_id(rec.tag_id).name + '\tid: ' + str(tag_list.get_tag_by_id(rec.tag_id).id) + '\tx= %.2f' % rez.x + ' \ty= %.2f' % rez.y + bcolors.reset)
                        if setup.visualise == True:
                            global graphQueue
                            graphQueue.put((rez, tag_list.get_tag_by_id(rec.tag_id).color))

                        if setup.rabbitmq == True:
                            today = datetime.datetime.today()
                            l = location_record(rec.tag_id, tag_list.get_tag_by_id(rec.tag_id).name, today, rez, tag_list.get_tag_by_id(rec.tag_id).aver_pos, color = tag_list.get_tag_by_id(rec.tag_id).color)
                            msg_txt = l.get_json() 
                            channel.basic_publish(exchange = '', routing_key = 'locations', body = msg_txt)

                            

                    # Помечаем использованные строки после калькуляции на удаление                        
                    for r2 in tag_list_for_location_engine:
                        r2.age = 100

                                
            # Фильтр старых записей на удаление
            ## Проверка на старые записи
        for rtd in self.__tag_records:
            if rtd.age > 99:
                self.__tag_records.remove(rtd)   
            rtd.age += 1

    def get_location(self, tag_id):
        loc = self.get_tag_by_id(tag_id)
        if loc == None: 
            return None
        return loc.last_pos
    
    def get_tags(self):
        return self.__tags

def convert_DW_time_to_s(time):
    return float(time / 1000000000.0)

class datastring:
    start = 0
    end = 0
    def __init__(self, start, end):
        self.start = start 
        self.end = end

def dist(loc_A, loc_B):
    return math.sqrt((loc_A.x - loc_B.x)**2 + (loc_A.y - loc_B.y)**2 + (loc_A.z - loc_B.z)**2)

def checkCRC(msg):
    if len(msg) == 32:
        # TODO Сделать нормальную проверку CRC
        if (msg[30] == 67) and (msg[31] == 82):
            return True
    return False

def prepare_string(msg):  
    # Поиск символа начала строки ":D"
    start_bytes_found = []
    pos = 0
    while pos < len (msg):
        start_bytes_pos = msg.find(b':D', pos)
        if start_bytes_pos != -1:
            start_bytes_found.append(start_bytes_pos)
        else:
            break
        pos = start_bytes_pos + 1
    
    end_bytes_found = []     
    '''
    # Поиск символа начала следующей строки ":D" или ":T" 
    # А нужно ли это вообще? Может надо ограничится поиском правильного CRC?
     
    pos = 0
    while pos < (len(msg) - 1):
        if (msg[pos] == 58) and ((msg[pos+1] == 84) or (msg[pos+1] == 68)): # Поиск символов ":D" или ":T" 
            # Надо понять, нужно ли оставлять поиск ":T", ведь в последней версии прошивки якоря не предусматривается 
            # штатнае трансляция всего потока rs485 на шлюз, а только адресованных ему пакетов
            end_bytes_pos = pos
            end_bytes_found.append(pos)
        else:
            end_bytes_pos = -1             
        pos = pos + 1
    '''
    # Если не найдены символы начала следующей строки, то ищем CRC в последних двух байтах с отступом 32 байта от start_bytes_found т.е. от ":D"
    pos = 0
    while pos < (len(msg) - 1):
        tmp_msg = []
        for i in range(pos, pos + 32):            
            if i < len(msg):
                tmp_msg.append(msg[i])
            i += 1 
        if len(tmp_msg) == 32 and checkCRC(tmp_msg) == True:
            end_bytes_found.append(pos + 32)
        tmp_msg.clear()
        pos += 1

    # А если CRC битый? 
    # Когда удалять последовательность от символа :D более 32 байт длиной, не имеющую окончания CRC?

    #print_debug_1("msg len = " + str(len(msg)))
    #print_debug_1("start found :D @")  
    #print_debug_1(start_bytes_found)
    #print_debug_1("end found :D|:T @")  
    #print_debug_1(end_bytes_found)

    dstr = []

    comb = 0
    if len(start_bytes_found) > 0:
        for x in range(0, len(start_bytes_found)):
            for y in range(0, len(end_bytes_found)):
                if (end_bytes_found[y] - start_bytes_found[x]) == 32:
                    comb += 1
                    #print_debug_1('Комбинация ' + str(comb) + ' x[' + str(x) + '] = ' + str(start_bytes_found[x]) + chr(msg[start_bytes_found[x]]) + ' y[' + str(y)+ '] = ' + str(end_bytes_found[y] - 1) + chr(msg[end_bytes_found[y] - 1]) )
                    d = datastring(start_bytes_found[x], end_bytes_found[y])
                    dstr.append(d)
        #print_debug_1(msg.decode('utf8'))
        
    rez = bytearray()    
    if len(dstr) > 0:    
        for i in range(0, dstr[0].start):
            msg.pop(0)
        #print_debug_1('После предварительной обрезки ' + msg.decode('utf8'))
        for i in range(0, 32):
            rez.append(msg[0])
            msg.pop(0)
        
        #print_debug_1('Результат ' + rez.decode('utf8'))    
        #print_debug_1('Остаток ' + msg.decode('utf8'))
        return rez
    
    # Отсечь бесполезные данные с нуля до первого включения :D
    cut_pos = msg.find(b':D', 0)
    if cut_pos == -1:
        msg.clear()
        return None     
    pos = 0    
    while pos < cut_pos:
        msg.pop(0)  
        pos += 1
    return None         



def parse_string(msg):
    val = msg
    if checkCRC(msg) == False:
        print_debug_1(bcolors.red + 'CRC err' + bcolors.reset)
        return None
  
    # Проверка 10-го бита
    # 0x00 - Блинк TDoA от метки
    if msg[10] == 0x00:
        format = '<xxIIBIQBHixx'
        dest_id, src_id, blink_type, tag_id, timestamp, blink_id, param_id, param_value = struct.unpack(format, val)
        r = record(dest_id, src_id, blink_type, tag_id, timestamp, blink_id, param_id, param_value)
        return r
    # 0x10 – Ranging Init Request Запрос на TWR от инициатора    
    elif msg[10] == 0x10:
        return None
    # 0x11 – Ranging Init Approval. Согласие на TWR от ответчика
    elif msg[10] == 0x11:
        return None
    # 0x12 – Poll

    # 0x13 – Response

    # 0x14 – Result

    # 0x30 – Передача команды  
    elif msg[10] == 0x30:
        format = '<xxIIBH17sxx'
        dest_id, src_id, cmd_type, cmd_number, data = struct.unpack(format, val)
        
        # Сообщения читаются как от якорей, так могут быть перенаправлены собственные от шлюза
        if cmd_number == 0xFFFF: # Пришло текстовое сообщение
            text_to_display = str()
            for t in data:
                if (t < 127) and (t > 31): 
                    text_to_display += chr(t)
                if t == 0:
                    break    
                    
            global anchor_list        
            #TODO добавить проверку существования anchor_list.get_anchor_by_id(src_id)
            if anchor_list.get_anchor_by_id(src_id) != None:
                print_debug_1(bcolors.cyan + str(anchor_list.get_anchor_by_id(src_id).name) + ': ' + text_to_display + bcolors.reset)
        return None   
    # 0x31 – Передача прошивки
    elif msg[10] == 0x31:
        return None # Обработка не требуется
    # 0x32 – Передача настроек 
    elif msg[10] == 0x32:
        return None # Обработка не требуется
    # 0x3A – Отмена процедуры передачи настроек по инициативе инициатора
    elif msg[10] == 0x3A:
        print_debug_1(bcolors.yellow + 'Отмена процедуры передачи настроек по инициативе инициатора' + bcolors.reset)
        return None # Обработка не требуется  
    # 0x3B – Отмена процедуры передачи настроек по инициативе получателя
    elif msg[10] == 0x3B:
        print_debug_1(bcolors.yellow + 'Отмена процедуры передачи настроек по инициативе получателя' + bcolors.reset)
        return None # Обработка не требуется     
    # 0x3E – Запрос подтверждения последнего успешного получения блока настроек/команды
    elif msg[10] == 0x3E:
        return None # Обработка не требуется
    # 0x3F – Подтверждение статуса последнего полученного блока настроек/команды
    elif msg[10] == 0x3F:
        global waiting_cmd_confirm
        waiting_cmd_confirm = 0
        print_debug_1(bcolors.yellow + 'cmd OK' + bcolors.reset)
        return None # Обработка не требуется 

    # 0xFF – Синхроблинк от синхромастера
    elif msg[10] == 0xFF: 
        return None # Обработка не требуется

    print_debug_1(bcolors.red + 'cmd err: str = ' + str(msg) + ' byte10 = ' + str(hex(msg[10])) + bcolors.reset)
    return None 

# Отправка команды одному устройству
def send_cmd(target_id, cmd, value):
    global waiting_cmd_confirm 
    #TODO Добавить ожидание ответа, проверку статуса и повторную отправку команды
    #TODO Добавить проверку типа value, т.е. данные или число и т.д.
    if waiting_cmd_confirm == 0:
        # Разложение адреса назначения на байты
        target_id_bytes = bytearray(target_id.to_bytes(4, byteorder='little')) 
        cmd_bytes = bytearray(cmd.to_bytes(2, byteorder='little'))
        value_bytes = bytearray(value.to_bytes(4, byteorder='little', signed = True))
        tx_msg = bytes([0x3A, 0x44, target_id_bytes[0], target_id_bytes[1], target_id_bytes[2], target_id_bytes[3], 0x00, 0x00, 0x00, 0x00, 0x30, cmd_bytes[0], cmd_bytes[1], value_bytes[0], value_bytes[1], value_bytes[2], value_bytes[3], 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x43, 0x52])
        #waiting_cmd_confirm = 1
        res = s.write(tx_msg)
        if res :
            print_debug_2(str(tx_msg).encode('utf8'))
        else:
            print_debug_2('tx timeout')
    return

# Универсальная отправка команды одному или всем устройствам с проверкой
# anchor_selected = anchor_list.index + 1
def send_cmd_all(anchor_list, anchor_selected, cmd_number, value):
    if anchor_selected == 0: 
        for i in range(0, anchor_list.len()):
            a = anchor_list.get_anchor_by_index(i)
            if a != None:
                send_cmd(a.id, cmd_number, value)
    else:
        if anchor_selected < anchor_list.len() + 1:
            send_cmd(anchor_list.get_anchor_by_index(anchor_selected - 1).id, cmd_number, value) 
        
def print_sel_anchor(a_list, a_selected):
    an_name = a_list.get_anchor_by_index(a_selected - 1).name
    an_id = str(a_list.get_anchor_by_index(a_selected - 1).id)
    print(bcolors.cyan + 'Выбран якорь: ' + an_name + '   id: ' + an_id + bcolors.reset)

def read_kbd_input(inputQueue):
    while (True):
        input_str = input() # Построчный ввод, обязательно подтверждение вводом
        #print_debug_1(input_str)
        inputQueue.put(input_str) 

def read_serial(serialQueue):
    while (True):
        input_serial = s.read(2048) # Чтение последовательно порта
        if input_serial != b'':
            #print_debug_1('ser read ' + str(len(input_serial)))
            serialQueue.put(input_serial)
            
        

# Координаты вершин пиктограммы якоря
def anchor_verts(x, y):
   v = [
       (x + 0, y - 0.3),  # left, bottom
       (x - 0.3, y + 0.3),  # left, top
       (x + 0.3, y + 0.3),  # right, top
       (x + 0, y - 0.3),  # ignored
   ]
   return v

def checkCMD(inpur_str):
    global anchor_selected
    if (inpur_str != ''):
        if (input_str == '0'):
            anchor_selected = 0 # Групповая рассылка    
            print(bcolors.cyan + 'Групповая рассылка' + bcolors.reset)
        elif (input_str == '1'):
            anchor_selected = 1 # Выбран AN_1    
            print_sel_anchor(anchor_list, anchor_selected)
        elif (input_str == '2'):
            anchor_selected = 2 # Выбран AN_2                
            print_sel_anchor(anchor_list, anchor_selected)
        elif (input_str == '3'):
            anchor_selected = 3 # Выбран AN_3                
            print_sel_anchor(anchor_list, anchor_selected)
        elif (input_str == '4'):
            anchor_selected = 4 # Выбран AN_4                
            print_sel_anchor(anchor_list, anchor_selected)
        elif (input_str == '5'):
            anchor_selected = 5 # Выбран AN_5
            print_sel_anchor(anchor_list, anchor_selected)
        elif (input_str == '6'):
            anchor_selected = 6 # Выбран AN_6
            print_sel_anchor(anchor_list, anchor_selected)
        elif (input_str == '7'):
            anchor_selected = 7 # Выбран AN_7
            print_sel_anchor(anchor_list, anchor_selected)
        elif (input_str == '8'):
            anchor_selected = 8 # Выбран AN_8
            print_sel_anchor(anchor_list, anchor_selected)
        elif (input_str == '9'):
            anchor_selected = 9 # Выбран AN_9
            print_sel_anchor(anchor_list, anchor_selected)

        elif (input_str == 'r'): # Сброс режима    
            send_cmd_all(anchor_list, anchor_selected, 0x0001, 0)
        
        elif (input_str == 't'): # Режим TDoA
            send_cmd_all(anchor_list, anchor_selected, 0x0002, 0)

        elif (input_str == 'm'): # Установить режим SyncMaster
            if anchor_selected > 0: # Нельзя всем присвоить Мастера
                send_cmd_all(anchor_list, anchor_selected, 0x0003, 0)
            else:
                print(bcolors.yellow + 'Выберите только один якорь' + bcolors.reset) 
        
        elif (input_str == 's'): # Установить режим SyncSlave    
            send_cmd_all(anchor_list, anchor_selected, 0x0004, 0)
        
        elif (input_str == 'i'): # Вывод информации и настроект по якорю    
            send_cmd_all(anchor_list, anchor_selected, 0xFFF0, 0)

        elif (input_str == 'w'): # Режим TWR
            return # Не готов пока 
        
        elif (input_str == 'init'): # Режим инициализации якоря    
            #if anchor_selected > 0:  
            return # Не готов пока 

        elif ('delay' in input_str): # Ввод задержки для SyncSlave
            spl = input_str.split()
            value = 0
            for v in spl:
                try:
                    value = int(v)
                    break
                except ValueError:
                    value = 0
            if anchor_selected > 0: # Нельзя всем присвоить одну и ту же задержку
                send_cmd_all(anchor_list, anchor_selected, 0x0010, value)
            else:
                print(bcolors.yellow + 'Выберите только один якорь' + bcolors.reset)    
          
        elif ('dist' in input_str): # Расстояние до синхроякоря ??? ПЕРЕДЕЛАТЬ ???? расстояние должно быть не до одного синхроякоря а до каждого 
            spl = input_str.split()
            value = 0
            for v in spl:
                if v.isdigit():
                    value = int(v)
                    break
            send_cmd_all(anchor_list, anchor_selected, 0x0011, value)   

        elif ('level' in input_str): # Уровень синхронизации 
            spl = input_str.split()
            value = 0
            for v in spl:
                if v.isdigit():
                    value = int(v)
                    break
            send_cmd_all(anchor_list, anchor_selected, 0x0012, value)   
        
        elif ('Ki' in input_str): # Коэф. ПИД Ki 
            spl = input_str.split()
            value = 0
            for v in spl:
                if v.isdigit():
                    value = int(v)
                    break
            send_cmd_all(anchor_list, anchor_selected, 0x0013, value)  

        elif ('Kd' in input_str): # Коэф. ПИД Kd 
            spl = input_str.split()
            value = 0
            for v in spl:
                if v.isdigit():
                    value = int(v)
                    break
            send_cmd_all(anchor_list, anchor_selected, 0x0014, value)  

        elif ('Kp' in input_str): # Коэф. ПИД Kp 
            spl = input_str.split()
            value = 0
            for v in spl:
                if v.isdigit():
                    value = int(v)
                    break
            send_cmd_all(anchor_list, anchor_selected, 0x0015, value)  
        
        elif ('pid_debug' in input_str): # Коэф. ПИД Kp 
            spl = input_str.split()
            print (spl)
            value = 0
            if ('On' in spl) or ('on' in spl) or ('1' in spl):
                send_cmd_all(anchor_list, anchor_selected, 0x0016, 1) 
            else:
                send_cmd_all(anchor_list, anchor_selected, 0x0016, 0) 
            

def print_debug_1(str):
    if setup.debug_output == 1:
        print(str)

def print_debug_2(str):
    if setup.debug_output == 2:
        print(str)

def show_graph(graphQueue):
    # Отображение меток и якорей
    fig, ax = plt.subplots()

    # Пиктограммы якорей
    codes = [
        Path.MOVETO,
        Path.LINETO,
        Path.LINETO,
        Path.CLOSEPOLY,
    ]

    global anchor_list
    for idx in range(0, anchor_list.len()):
        v = anchor_verts(anchor_list.get_anchor_by_index(idx).x, anchor_list.get_anchor_by_index(idx).y)
        path = Path(v, codes)
        patch = patches.PathPatch(path, facecolor='orange', lw=2)
        ax.add_patch(patch)

    # Настройки поля
    ax.set_aspect('equal')
    x_min = 0
    y_min = 0
    x_max = 0
    y_max = 0

    for a in anchor_list.get_anchors():
        if x_min > a.x:
            x_min = a.x
        if y_min > a.y:
            y_min = a.y
        if x_max < a.x:
            x_max = a.x
        if y_max < a.y:
            y_max = a.y
        

    plt.xlim(x_min - 5, x_max + 5)
    plt.ylim(y_min - 5, y_max + 5)
    plt.grid(True)
    plt.show(False)
    plt.draw()
    background = fig.canvas.copy_from_bbox(ax.bbox)

    #point = Ellipse((10, 10), 1, 1, 0)
    #ax.draw_artist(point)
    plt.pause(0.1)
    while (True):
        if (graphQueue.qsize() == 0):
            plt.pause(0.01)
            continue
        loc, tag_color = graphQueue.get()
        
        points = ax.plot(loc.x, loc.y, 'o', color = tag_color)[0]

        # restore background
        fig.canvas.restore_region(background)

        # redraw just the points
        ax.draw_artist(points)

        # fill in the axes rectangle
        fig.canvas.blit(ax.bbox)
                        
        plt.pause(0.01)


class bcolors:
    reset = '\033[0m'
    bold = '\033[1m'
    underline = '\033[4m'

    black = '\033[90m'
    red = '\033[91m'
    green = '\033[92m'
    yellow = '\033[93m'    
    blue = '\033[94m'
    purple = '\033[95m'
    cyan = '\033[96m'
    white = '\033[97m'

class script_setup:
    # debug_output = 0 - нет вывода отладки, только координаты, 1 - вывод базовой отладочной информации, 2 - расширенный вывод
   
    def __init__(self, terminal_input = True, debug_output = 0, record = False, visualise = False, serial_port = 'COM14', rabbitmq = False, rabbitmq_server = "192.168.4.101", rabbitmq_user = "User1", rabbitmq_pwd = "user1", filter = True, filter_K = 0.1):
        self.terminal_input = terminal_input
        self.debug_output = debug_output
        self.record = record
        self.visualise = visualise
        self.serial_port = serial_port
        self.rabbitmq = rabbitmq
        self.rabbitmq_server = rabbitmq_server
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pwd = rabbitmq_pwd
        self.filter = filter
        self.filter_K = filter_K

def exit_handler():
    if setup.rabbitmq == True:
        connection.close()
    if setup.record == True:
        csvfile.close()

    '''
    serialThread.start()
    if setup.terminal_input == True:        
        inputThread.end()

    if setup.visualise == True:
        graphThread.start()
    '''
    print ("Exiting location engine")

# ********************************************************
# Text
# ********************************************************

# TODO Настройки якорей в json файл
# TODO Настройки меток в json файл
# TODO Графическое отображение координат
# TODO Методы определения координат по TDoA и TWR
# TODO Проверка пришедшего пакета на легальность меток и якорей
setup = script_setup()

if __name__ == '__main__':
    if len (sys.argv) == 1:
        # Настройки программы по умолчанию
        print('Настройки программы по умолчанию')
    else: 
        # Обработка параметров командной строки
        # При передачи одного параметра, оставшиеся неуказанные параметры будут установлены в False  

        # Отображать простую визуализацию
        if '-v' in sys.argv:
            setup.visualise = True
            print('Визуализация включена')
        else:
            setup.visualise = False

        # Запись данных в файл
        if '-r' in sys.argv:
            setup.record = True
            print('Запись данных в файл')
        else:
            setup.record = False

        # Настройка com порта
        if '-serial' in sys.argv:
            param_idx = sys.argv.index('-serial')
            if len(sys.argv) > (param_idx + 1):
                parav_value = sys.argv[param_idx + 1]
                setup.serial_port = parav_value
                print('Serial port: %s' % parav_value)
        else:
            setup.serial_port = 'COM14'  # значение по умолчанию  
        
        # Вывод 2-х уровневой отладочной информации в консоль
        if ('-d' in sys.argv) or ('-d1' in sys.argv) or ('-d2' in sys.argv):
            if ('-d' in sys.argv) or ('-d1' in sys.argv):
                setup.debug_output = 1
                print('Вывод отладочной информации в консоль: уровень 1')
            else:
                setup.debug_output = 2    
                print('Вывод отладочной информации в консоль: уровень 2')
        else:
            setup.debug_output = 0

        # Ввод команд через консоль 
        if '-i' in sys.argv:
            setup.terminal_input = True
            print('CLI')
        else:
            setup.terminal_input = False

        # Передача координат и прочих данных на сервер rabbitmq
        if '-rabbitmq' in sys.argv: # -rabbitmq localhost user1 userpwd
            setup.rabbitmq = True
            param_idx = sys.argv.index('-rabbitmq')
            if len(sys.argv) > (param_idx + 1):
                parav_value = sys.argv[param_idx + 1]
                setup.rabbitmq_server = parav_value
                print('Rabbitmq server: %s' % parav_value)
        else:
            setup.rabbitmq = False 

        # Применение фильтра на измеренные координаты
        if '-filter' in sys.argv: # -filter 0.1
            setup.filter = True
            param_idx = sys.argv.index('-filter')
            if len(sys.argv) > (param_idx + 1):
                parav_value = float(sys.argv[param_idx + 1])
                if (parav_value > 0) and (parav_value <= 1):
                    setup.filter_K = parav_value
                else:
                    setup.filter_K = 0.1 # значение по умолчанию
                print('Filter K = %s' % parav_value)
        else:
            setup.filter = False 

    # Обработчик при выходе из скрипта
    atexit.register(exit_handler)

    anchor_list = anchors()

    #TODO Добавить чтение настроек из json файла
    '''
    # Тестовый набор якорей
    an1 = anchor('AN1', 2149056513, x = 50, y = 0, z = 0)
    an2 = anchor('AN2', 2149056514, x = 0, y = 300, z = 0)
    an3 = anchor('AN3', 2149056515, x = 350, y = 350, z = 0)
    an4 = anchor('AN4', 2149056516, x = 400, y = 50, z = 0)
    anchor_list.add_anchor(an1)
    anchor_list.add_anchor(an2)
    anchor_list.add_anchor(an3)
    anchor_list.add_anchor(an4)
    '''
    # Реальные якоря
    anchor_list.add_anchor(anchor('AN_1', 4587578, 5.15, 7.92, 0))
    anchor_list.add_anchor(anchor('AN_2', 2424876, 0.25, 7.93, 0))
    anchor_list.add_anchor(anchor('AN_3', 1900591, 0, 0, 0))
    anchor_list.add_anchor(anchor('AN_4', 2162732, 0, 0, 0))
    anchor_list.add_anchor(anchor('AN_5', 4063277, 5.15, 0.46, 0))
    anchor_list.add_anchor(anchor('AN_6', 3801133, 0.21, 0.48, 0))
    
    tag_list = tags()

    # Метки для симулятора 
    tag_list.add_tag(tag('Tag1', 0x20000001, 'black'))
    tag_list.add_tag(tag('Tag2', 0x20000002, 'red'))
    tag_list.add_tag(tag('Tag3', 0x20000003, 'yellow'))
    tag_list.add_tag(tag('Tag4', 0x20000004, 'blue'))
    tag_list.add_tag(tag('Tag5', 0x20000005, 'green'))
    tag_list.add_tag(tag('Tag6', 0x20000006, 'grey'))
    tag_list.add_tag(tag('Tag7', 0x20000007, 'magenta'))
    tag_list.add_tag(tag('Tag8', 0x20000008, 'orange'))
    tag_list.add_tag(tag('Tag9', 0x20000009, 'silver'))
    tag_list.add_tag(tag('Tag10', 0x20000010, 'cyan'))

    # Реальные метки
    tag_list.add_tag(tag('Tag_1', 1835046, 'red'))
    tag_list.add_tag(tag('Tag_2', 2097190, 'blue'))
    tag_list.add_tag(tag('Tag_3', 1835051))
    tag_list.add_tag(tag('Tag_4', 1769515, 'magenta'))
    tag_list.add_tag(tag('Tag_5', 1966123, 'silver'))
    tag_list.add_tag(tag('Tag_6', 1966118, 'cyan'))

    # Инициализация цветного модуля
    init()

    # Настройка COM порта
    s = serial.Serial(
        port = setup.serial_port,
        baudrate = 921600, 
        parity = serial.PARITY_NONE,
        stopbits = serial.STOPBITS_ONE,
        timeout = 0.1,
        bytesize = serial.EIGHTBITS
    )


    # Файл для записи лога
    csvfilename = time.strftime('%y%m%d_%H%M')
    if setup.record == True:
        csvfile = open('c:\\PythonProjects\\gate\\gate\\location_server\\logs\\' + csvfilename + '.txt', 'a', newline='') 
        fieldnames = ['time', 'tag_id', 'tag_name', 'blink_id']
        for a in anchor_list.get_anchors():
            fieldnames.append(a.name)        
        fieldnames = fieldnames + ['last_pos_x', 'last_pos_y', 'last_pos_z', 'aver_pos_x', 'aver_pos_y', 'aver_pos_z']        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

    parse = 0
    msg = bytearray()

    # Поток чтения клавиатуры (отладка)
    if setup.terminal_input == True:
        inputQueue = queue.Queue()
        inputThread = threading.Thread(target=read_kbd_input, args=(inputQueue,), daemon=True)
        inputThread.start()

    # Поток чтения com порта
    serialQueue = queue.Queue()
    serialThread = threading.Thread(target=read_serial, args=(serialQueue,), daemon=True)
    serialThread.start()

    # Поток отображения точек через matplotlib
    if setup.visualise == True:
        graphQueue = queue.Queue()
        graphThread = threading.Thread(target=show_graph, args=(graphQueue,), daemon=True)
        graphThread.start()

    if setup.rabbitmq == True:
        connection = pika.BlockingConnection(pika.ConnectionParameters(setup.rabbitmq_server, credentials = pika.PlainCredentials(setup.rabbitmq_user, setup.rabbitmq_pwd)))
        channel = connection.channel()
        channel.queue_declare(queue='locations', durable =True)


    anchor_selected = 0

    # Основной цикл
    while True:
        if setup.terminal_input == True:
            if (inputQueue.qsize() > 0):
                input_str = inputQueue.get()
                inputQueue.task_done()
                checkCMD(input_str)
                
        # Чтение приема последовательного порта, если очередь не пуста, то обрабатываем содержимое
        if (serialQueue.qsize() == 0):
            continue
        res = serialQueue.get()
        serialQueue.task_done()
        msg.extend(bytearray(res))

        while len(msg) >= (32):
            # Проверяем массив msg только при условии что он не менее 32 байт
            rez_str = prepare_string(msg)
            if rez_str == None:
                break

            rec = parse_string(rez_str)
            
            # Если возврат после парсинга строки не пустой, то обрабатываем полученную строку
            if rec != None:
                #TODO проверить соответствуют ли якоря и метки имеющимся в списке
                # Проверка по якорям
                if anchor_list.get_anchor_by_id(rec.src_id) != None:
                    # Проверка по меткам
                    if tag_list.get_tag_by_id(rec.tag_id) != None:
                        # Якорь и метка есть в базе, значит полученная запись корректна и можно ее обрабатывать
                        print_debug_1(bcolors.black + 'Якорь: ' + anchor_list.get_anchor_by_id(rec.src_id).name + ' id: ' + str(rec.src_id) + '  Метка: ' + tag_list.get_tag_by_id(rec.tag_id).name + ' id: ' + str(rec.tag_id) + '  Номер блинка: ' + str(rec.blink_id) + '  Время: ' + str(rec.timestamp) + bcolors.reset)  
                        tag_list.add_record(rec)
                        tag_list.calc_location(anchor_list)
                    else:
                        print_debug_1(bcolors.red + 'Метка не найдена: ' + str(rec.tag_id) + bcolors.reset)
                else:
                        print_debug_1(bcolors.red + 'Якорь не найден: ' + str(rec.src_id) + bcolors.reset)





    

