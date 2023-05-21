from typing import List
from variables import *
import telnetlib
import re
import requests
import json
import time
import sys

def getPassword(deviceIP, port):
    # Function to return password for specific device types using its IP address

    # call getDeviceInfo API
    url = f'http://{device_IP}:{port}/API10/getDeviceInfo'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if 'Device Type' in data:
            device_type = data['Device Type']
            print("Device type:", device_type)
        else:
            print("Device type not found in response.")
        if 'WiFi MAC' in data:
            mac_value = data['WiFi MAC']
            mac_add = ''.join(mac_value.split(':'))
            print("MAC :", mac_add)
    else:
        print("Failed to get response. Status code:", response.status_code)
        return "SKIP"

    if device_type < 200:
        print("Switching environments is not supported for Device type less than 200")
        print(" skip running the test case")
        return "SKIP"
    elif device_type in agent_update:
        print('2k Indoor and 4k Floodlight can be moved to Prod/QA only via AGENT update')
        print(f'Skip: Device type {device_type} with Device IP {device_IP}')
        return "SKIP"
    elif device_type == 200:
        password = '6366q+7682'
    elif device_type in aoni_devices:
        password = 'a0n1ipc'
    elif device_type in skl_devices:
        password = 'IngT20Z'
    elif device_type in augentix_devices:
        password = 'HC1752+@ug'
    elif device_type in new_devices:
        password = ''
        for i in range(len(mac_add)):
            if i % 2 != 0:
                password += mac_add[i]
    else:
        print(f'Password not found for Device type: {device_type}')

    return password, mac_add, device_type


def enableTelnet(deviceIP, port):
    # Function to enable telnet with IP

    # call enableTelnet API
    url = f'http://{device_IP}:{port}/API10/telnetControl'
    payload = json.dumps({
        "enable": 1
    })
    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    if response.status_code == 200:
        print(f"Telnet session enabled for {deviceIP}")
    else:
        print(f"Error: Telnet for {deviceIP} failed")

    return response.status_code


def getDeviceLocations(mac_add, device_type):
    if device_type in aoni_devices:
        configPath = "{}/endpoint.cfg".format(aoniPath)
        keyPath = aoniPath + '/' + mac_add + ".keys"
        shadowPath = aoniShadowPath
    elif device_type in new_devices:
        print()
    elif device_type in skl_devices:
        print()
    elif device_type in augentix_devices:
        print()
    else:
        print(f"File locations not found for Mac {mac_add}")
        return "SKIP"

    return configPath, keyPath, shadowPath


def switchenvironment(device_ip, password, targetEnv, mac_add, device_type, configPath, keyPath, shadowPath):
    global line_number
    tn = telnetlib.Telnet(device_ip, 23)
    response = tn.read_until(b"\n", 5)
    if re.search(".*login:", response.decode()):
        tn.write(b"root\n")
        tn.read_until(b"Password: ")
        tn.write(f"{password}\n".encode('ascii'))

    if tn.read_until(b"#"):
        print("You are connected")

    grep_command = f"grep -En -m 1 '\\.qa\\.swannsecurity' {configPath} \n".encode()

    tn.write(grep_command)
    output = tn.read_until(b'#').decode()
    print(output)

    qa_line_number = getLinenumber(output)

    grep_command = f"grep -Env '\\.qa' {configPath} | grep -m 1 'swannsecurity' \n".encode()

    tn.write(grep_command)
    output = tn.read_until(b'#').decode()
    print(output)

    prod_line_number = getLinenumber(output)
    print(qa_line_number)
    print(prod_line_number)

    if targetEnv == 'QA':
        sed_command = f"sed -i '{qa_line_number}s/^.*$/[default]/' {configPath}\n".encode()
        tn.write(sed_command)

        sed_command = f"sed -i '{prod_line_number}s/^.*$/[prod]/' {configPath}\n".encode()
        tn.write(sed_command)
    else:
        sed_command = f"sed -i '{qa_line_number}s/^.*$/[QA]/' {configPath}\n".encode()
        tn.write(sed_command)

        sed_command = f"sed -i '{prod_line_number}s/^.*$/[default]/' {configPath}\n".encode()
        tn.write(sed_command)

    if tn.read_until(b"#"):
        print("You are connected")

    tn.write(f" rm {keyPath}\n".encode('ascii'))
    output = tn.read_until(b'#').decode()
    print(output)

    tn.write(f" rm {shadowPath}\n".encode('ascii'))
    output = tn.read_until(b'#').decode()
    print(output)

    time.sleep(2)
    tn.write(b"reboot\n")

    tn.close()


def getLinenumber(output):
    match = re.search(r"(\d+):", output)
    if match:
        line_number = int(match.group(1))
        line_number -= 1
    else:
        print("No match found.")
        exit()
    return (line_number)


if len(sys.argv) > 1:
    input_file = sys.argv[1]
else:
    print("Usage: python checking.py <input_file>")
    sys.exit(1)

with open(input_file, 'r') as file:
    for line in file:
        device_IP, port, targetEnv = line.strip().split(' ')
        password, mac_addr, device_type = getPassword(device_IP, port)
        if password != "SKIP":
            result = enableTelnet(device_IP, port)
            if result == 200:
                targetEnv = 'Prod'
                locationOutput = getDeviceLocations(mac_addr, device_type)
                if locationOutput == "SKIP":
                    print(f"SKIP - Switch env for {device_IP} file path cannot be found")
                    break
                else:
                    configPath, keyPath, shadowPath = locationOutput
                    switchenvironment(device_IP, password, targetEnv, mac_addr, device_type, configPath, keyPath, shadowPath)
            else:
                print(f"Switching environment for Device: {device_IP} - Mac {mac_addr} failed since telnet not "
                      f"established")
        else:
            print(f"Switching environment for Device: {device_IP} failed- Password not obtained for device")
