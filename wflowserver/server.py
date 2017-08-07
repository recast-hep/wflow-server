import os
import wflowcelery.backendtasks
from wflowcelery.fromenvapp import app as celery_app
from flask import Flask, request, jsonify
import jobdb
import wflowhandlers
import uuid
import json
import logging

logging.basicConfig(level = logging.INFO)
log = logging.getLogger(__name__)
app = Flask(__name__)

SECRET_KEY = "asdfasdfasdf"

@app.route('/workflow_submit', methods = ['POST'])
def wflow_submit():
    workflow_spec = request.json
    queue = workflow_spec.pop('queue','default')
    jobguid = str(uuid.uuid4())

    context = wflowhandlers.request_to_context(workflow_spec, jobguid)

    log.info('submitting workflow to queue {}'.format(queue,context))
    result = wflowcelery.backendtasks.run_analysis.apply_async((
                                                     wflowcelery.backendtasks.setupFromURL,
                                                     wflowcelery.backendtasks.generic_onsuccess,
                                                     wflowcelery.backendtasks.cleanup,
                                                     context),
                                                     queue = queue)

    jobdb.register_job(jobguid,result.id)
    return jsonify({
        'id':jobguid
    })

@app.route('/workflow_status', methods = ['GET'])
def wflow_status():
    wflow_ids = request.json['workflow_ids']
    log.info('checking status for %s workflow ids',len(wflow_ids))
    return jsonify({'status_codes': [jobdb.job_status(wflowid) for wflowid in wflow_ids]})

@app.route('/subjob_msgs', methods = ['GET'])
def subjob_msg():
    subjob_id = request.json['subjob_id']
    topic     = request.json['topic']
    json_lines = open(os.path.join(os.environ['WFLOW_SUBJOB_BASE'],os.environ['WFLOW_SUBJOB_TEMPLATE'].format(subjob_id,topic))).readlines()
    return jsonify({'msgs':[json.loads(line) for line in json_lines]})

@app.route('/workflow_msgs', methods = ['GET'])
def wflow_msgs():
    return jsonify({'msgs':[]})

@app.route('/jobs', methods = ['GET'])
def jobs():
    return jsonify({'jobs':jobdb.all_jobs()})


@app.route('/pubsub_server', methods = ['GET'])
def pubsub_server():
    return jsonify(dict(
        host = os.environ['WFLOW_CELERY_REDIS_HOST'],
        db   = os.environ['WFLOW_CELERY_REDIS_DB'],
        port = os.environ['WFLOW_CELERY_REDIS_PORT'],
        channel = 'logstash:wflowout'
    ))

if __name__ == '__main__':
    app.run(host = '0.0.0.0', port=os.environ.get('WFLOW_SERVER_PORT',5000))