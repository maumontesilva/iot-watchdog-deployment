from flask import Flask, jsonify, make_response, request, abort
import subprocess
import time
import uuid
import os
import logging
import json
import couchdb

logging.basicConfig(filename='iot-watchdog-deployment.log',level=logging.DEBUG)

app = Flask(__name__)

couch = couchdb.Server('http://192.168.56.101:5984/')

@app.route('/iot-watchdog/api/v1.0/deploy/agent', methods=['POST'])
def deploy_iot_watchdog_agent():
    logging.info("Deploy IoT Watchdog agent called ...")
    if not request.json:
        logging.error("No body sent.")
        abort(400)
    if not 'host' in request.json \
        or not 'username' in request.json \
        or not 'password' in request.json:
        logging.error("Missing required properties.")
        abort(400)

    host = request.json["host"]
    username = request.json["username"]
    password = request.json["password"]
    UUID = str(uuid.uuid4())

    logging.debug("HOST: " + host)
    logging.debug("USERNAME: " + username)
    logging.debug("UUID: " + UUID)

    try:
        install_iot_watchdog(host, username, password, UUID)
        deviceFileFolder = collect_device_facts(host, username, password, UUID)
        persistDeviceProfile(deviceFileFolder, host)
    except Exception as error:
        logging.error(error)
        abort(500)

    return jsonify({'result': 'ok'}), 201

@app.route('/iot-watchdog/api/v1.0/facts/<int:device_uuid>', methods=['GET'])
def get_device_fatcs(device_uuid):
    return jsonify({'tasks': 'ee'})

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

@app.errorhandler(400)
def not_found(error):
    return make_response(jsonify({'error': 'Invalid request format'}), 404)

def install_iot_watchdog(host, username, password, uuid):
    logging.info("installing IoT Watchdog agent ...")

    command = "ansible-playbook roles/deployment/tasks/main.yml" \
              " -i hosts" \
              " -e \"ansible_user={1} ansible_ssh_pass={2} ansible_sudo_pass={2}\" " \
              " --extra-vars=\"source_code=../../../iot-device/agent/" \
              " iot_watchdog_agent_uuid={3}" \
              " iot_watchdog_agent_need_registration={4}" \
              " service_def=../../../iot-device/service/\"".format(host, username, password, uuid, "yes")

    return_code = run_cmd(command)
    if return_code > 0:
        errorMsg = 'Error installing IoT Watchdog agent. Error code: ' + str(return_code)
        logging.error(errorMsg)
        raise Exception(errorMsg)

def collect_device_facts(host, username, password, uuid):
    logging.info("collecting device facts ...")

    tmpFolder = "tmp/" + uuid;
    logging.debug("Facts will be stored on " + tmpFolder)

    if not os.path.exists(tmpFolder):
        os.makedirs(tmpFolder)

    command = "ansible {0} -e \"ansible_user={1} ansible_ssh_pass={2} ansible_sudo_pass={2}\"" \
              " -m setup --tree {3}".format(host, username, password, tmpFolder);

    return_code = run_cmd(command)
    if return_code > 0:
        errorMsg = 'Error collecting device data. Error code: ' + str(return_code)
        logging.error(errorMsg)
        raise Exception(errorMsg)

    return tmpFolder

def run_cmd(command):
    logging.info("running command ...")
    logging.debug("CMD : " + command)
    p = subprocess.Popen(command, shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    while p.poll() is None:
        logging.debug("waiting command execution ...")
        time.sleep(5)

    logging.info("command returned code " + str(p.returncode))
    return p.returncode

def persistDeviceProfile(folderPath, host):
    with open(folderPath + '/' + host) as f:
        data = json.load(f)

    db = couch['deployment-db']
    db.save(data)

if __name__ == '__main__':
    logging.info("Starting IoT Watchdog deployment service ...")
    app.run(debug=True)