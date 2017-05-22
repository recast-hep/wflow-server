import os
import recastcelery.backendtasks
from recastcelery.fromenvapp import app as celery_app
from recastcelery.messaging import socketlog, get_stored_messages
from flask import Flask, request, jsonify
import jobdb
import wflowhandlers
import uuid
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
    result = recastcelery.backendtasks.run_analysis.apply_async((
                                                     recastcelery.backendtasks.setupFromURL,
                                                     recastcelery.backendtasks.generic_onsuccess,
                                                     recastcelery.backendtasks.cleanup,
                                                     context),
                                                     queue = queue)

    jobdb.register_job(jobguid,result.id)
    socketlog(jobguid,'workflow registered. processed by celery id: {}'.format(result.id))
    return jsonify({
        'id':jobguid
    })

@app.route('/workflow_status', methods = ['GET'])
def wflow_status():
    wflow_ids = request.json['workflow_ids']
    log.info('checking status for %s workflow ids',len(wflow_ids))
    return jsonify([jobdb.job_status(wflowid) for wflowid in wflow_ids])

@app.route('/workflow_msgs', methods = ['GET'])
def wflow_msgs():
    return jsonify(get_stored_messages(request.json['workflow_id']))

@app.route('/jobs', methods = ['GET'])
def jobs():
    return jsonify(jobdb.all_jobs())


@app.route('/pubsub_server', methods = ['GET'])
def pubsub_server():
    return jsonify(dict(
        host = os.environ['RECAST_CELERY_REDIS_HOST'],
        db   = os.environ['RECAST_CELERY_REDIS_DB'],
        port = os.environ['RECAST_CELERY_REDIS_PORT'],
        channel = 'socket.io#emitter'
    ))

if __name__ == '__main__':
    app.run(host = '0.0.0.0')