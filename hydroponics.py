import os
import glob
import time
import pprint
import MySQLdb
import requests
from datetime import datetime
import Adafruit_DHT

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

db = MySQLdb.connect(
    host="192.168.1.12",
    user="hydro",
    passwd="bsod4041$",
    db="hydroponics"
)
base_dir = '/sys/bus/w1/devices/'
device_folders = glob.glob(base_dir + '28*')
pp = pprint.PrettyPrinter(indent=2)
headers = {"content-type": "application/json"}
ambient_sensor = Adafruit_DHT.DHT11
ambient_sensor_pin = 17
sensor_list = {'28-0000054fff5f': 'Tube 1', '28-0000055001df': 'Tube 3',
               '28-00000550dd8f': 'Tank', '28-00000551218c': 'Tube 2'}


def read_temp_raw(device_file):
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines


def read_temp(device_file):
    lines = read_temp_raw(device_file)
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw(device_file)
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos + 2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_f, temp_c


def create_ambient_sensor(value, reading_type, unit):
    return (
        "dht11",
        "ambient_sensor_{type}".format(type=reading_type),
        unit,
        value,
        datetime.now(),
        datetime.now()
    )


def create_cpu_temp():
    # Return CPU temperature as a character string
    res = os.popen('vcgencmd measure_temp').readline()
    reading = (float(res.replace("temp=", "").replace("'C\n", "")) * 9 / 5) + 32
    return (
        "rpi",
        "cpu temperature",
        "Farenheit",
        reading,
        datetime.now(),
        datetime.now()
    )


def read_temps():
    while True:
        sensors = []
        for folder in device_folders:
            sensor = folder.split("/")[-1:][0]
            device_file = folder + '/w1_slave'
            sensor_data = (
                sensor,
                sensor_list[sensor],
                "Farenheit",
                read_temp(device_file)[0],
                datetime.now(),
                datetime.now()
            )
            sensors.append(sensor_data)

        humidity, temperature = Adafruit_DHT.read_retry(
            ambient_sensor, ambient_sensor_pin)
        sensors.append(create_ambient_sensor(humidity, "humidity", "percent"))
        sensors.append(create_ambient_sensor(
            (temperature * 9 / 5) + 32, "temperature", "Farenheit"))
        sensors.append(create_cpu_temp())
        insert_readings(sensors)
        pp.pprint(sensors)
        send_to_thingspeak(sensors)
        time.sleep(5)


def send_to_thingspeak(sensors):
    payload = {'api_key': 'EL2FNOQFS5H9WTAV'}
    for index, sensor in enumerate(sensors):
        payload["field{num}".format(num=index + 1)] = sensor[3]
    response = requests.post(
        'https://api.thingspeak.com/update.json', data=payload)
    print(response.status_code)


def insert_readings(sensors):
    cursor = db.cursor()
    cursor.executemany(
        """INSERT INTO sensors (address, name, unit, reading, created_at, updated_at)
      VALUES (%s, %s, %s, %s, %s, %s)""", sensors)
    db.commit()
    cursor.close()

if __name__ == "__main__":
    read_temps()
