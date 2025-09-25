#!/usr/bin/env python
import csv
import genie
import pyats
import pandas as pd
import json
import mysql.connector

# Seed IP i used in CP devcie...
seed_ip='10.47.69.101'
local_hostname = 'au-cpk-lv10-corp-esw01' #Later this can be collected by running 'show running-config | i hostname', for now manuly defined
site_id = 'AU-CPK'

# Connect to the MySQL database
cnx = mysql.connector.connect(
    host='localhost',
    user='xxxxxxxx',
    password='xxxxxxxxx',
    database='cdp_discovery',
    auth_plugin='mysql_native_password'
)

#from genie.libs.parser.ios.show_cdp import ShowCdpNeighborsDetail
from credentials import username, password, jumphost1, local_hostname
from netmiko import ConnectHandler
from genie import parsergen
import  netmiko_multihop


def discovery_job(device_ip, site):

    # Create a Netmiko connection to the device
    device = {
        "device_type": "cisco_ios",
        "ip": device_ip,
        "username": username,
        "password": password,
        "port": 22,
    }

    try:
        #Connect to Jump Host
        ssh = ConnectHandler(**jumphost1)
        #Connect to the end devcie
        net_connect = ssh.jump_to(**device)
        #net_connect = ConnectHandler(**device)
        #get the 'show cdp neighbors detail'
        output = net_connect.send_command('show cdp neighbors detail', use_textfsm=True)
        #get the 'hostname'
        output_hostname = net_connect.send_command('show running-config | i hostname', use_textfsm=True)
        #output = net_connect.send_command('show cdp neighbors detail', use_genie=True)
        #device_id = output.q.contains('device_id')
        #print(output)
        # Write JSON data to a CSV file
        json_str = json.dumps(output)
        df = pd.read_json(json_str)
        #print(df)
        df.to_csv('output.csv')

        # parse json object
        obj = json.loads(json_str)

        # Insert data into the database, with IGNORE to ignore the duplicates, 'destination_host' is a PRIMARY KEY in DB
        cursor = cnx.cursor()
        for CDP_DATA in obj:
            sql_discovery_insert = "INSERT IGNORE INTO neighbour_details (local_hostname, device_ip, site, destination_host, management_ip, platform, remote_port, local_port, software_version, capabilities ) VALUES (%s, %s, %s,%s,%s,%s,%s,%s,%s,%s)"
            input_data_discovery_insert = (local_hostname, device_ip, site, CDP_DATA["destination_host"], CDP_DATA["management_ip"], CDP_DATA["platform"], CDP_DATA["remote_port"], CDP_DATA["local_port"], CDP_DATA["software_version"], CDP_DATA["capabilities"])
            cursor.execute(sql_discovery_insert, input_data_discovery_insert)
        cnx.commit()
        cursor.close()

        # Update seed devices details in DB
        cursor = cnx.cursor()
        sql_seed_update = "UPDATE neighbour_details SET seed_dev = 'TRUE' where capabilities like '%Switch%'"
        cursor.execute(sql_seed_update)
        cnx.commit()
        cursor.close()
        #for i in obj:
        #    if i['capabilities'] == "Router Switch IGMP":
        #        #print(i)
        #        json_str = json.dumps(i)
        #        json_str_1 = pd.DataFrame([json_str])
        #        df = pd.read_json(json_str_1)
        #        df.to_csv('dev_output.csv')
        #        print(df)

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Close the Netmiko connection
        net_connect.disconnect()

discovery_job(seed_ip, site_id)

# Search for seed devices, where we need to build the loop
cursor = cnx.cursor()
sql_seed_update = "select destination_host, management_ip from neighbour_details where seed_dev = %s and site = %s"
input_data_search = ('TRUE', site_id)
cursor.execute(sql_seed_update, input_data_search)
all_other_seed = cursor.fetchall()
print(all_other_seed)
