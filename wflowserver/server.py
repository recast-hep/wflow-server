import os
from flask import Flask, request, jsonify
import wflowdb
import wflowhandlers
import uuid
import json
import logging
import click

logging.basicConfig(level = logging.INFO)
log = logging.getLogger(__name__)
app = Flask(__name__)
app.debug = True

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('WFLOW_DATABSE_URI','postgres://localhost')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

wflowdb.db.init_app(app)
SECRET_KEY = "asdfasdfasdf"

@app.route('/workflow_submit', methods = ['POST'])
def wflow_submit():
    workflow_spec = request.json
    queue = workflow_spec.pop('queue','default')
    jobguid = str(uuid.uuid4())

    context = wflowhandlers.request_to_context(workflow_spec, jobguid)

    wflowdb.register_wflow(context,queue)
    return jsonify({
        'id':jobguid
    })

@app.route('/workflow_config', methods = ['GET'])
def wflow_config():
    wflow_ids = request.json['workflow_ids']
    log.info('checking configs for %s workflow ids',len(wflow_ids))
    return jsonify({'configs': [wflowdb.wflow_config(wflowid) for wflowid in wflow_ids]})

@app.route('/workflow_status', methods = ['GET'])
def wflow_status():
    wflow_ids = request.json['workflow_ids']
    log.info('checking status for %s workflow ids',len(wflow_ids))
    return jsonify({'status_codes': [wflowdb.wflow_status(wflowid) for wflowid in wflow_ids]})

@app.route('/subjob_msgs', methods = ['GET'])
def subjob_msg():
    subjob_id = request.json['subjob_id']
    topic     = request.json['topic']
    try:
        json_lines = open(os.path.join(os.environ['WFLOW_SUBJOB_BASE'],os.environ['WFLOW_SUBJOB_TEMPLATE'].format(subjob_id,topic))).readlines()
        return jsonify({'msgs':[json.loads(line) for line in json_lines]})
    except IOError:
        return jsonify({'msgs':[]})

@app.route('/workflow_msgs', methods = ['GET'])
def wflow_msgs():
    workflow_id = request.json['workflow_id']
    topic = request.json['topic']
    try:
        json_lines = open(os.path.join(os.environ['WFLOW_WFLOW_BASE'],os.environ['WFLOW_WFLOW_TEMPLATE'].format(workflow_id,topic))).readlines()
        return jsonify({'msgs':[json.loads(line) for line in json_lines]})
    except IOError:
        return jsonify({'msgs':[]})

@app.route('/wflows', methods = ['GET'])
def wflows():
    return jsonify({'wflows':wflowdb.all_wflows()})

@app.route('/pubsub_server', methods = ['GET'])
def pubsub_server():
    return jsonify(
        url = os.environ['WFLOW_BACKEND_REDIS_URL']
        channel = 'logstash:out'
    ))

@click.group()
def cli():
    pass

@cli.command()
@click.option('--create', default = True)
def run_server(create):
    if create:
        with app.app_context():
            wflowdb.db.create_all()
    app.run(host = '0.0.0.0', port=int(os.environ.get('WFLOW_SERVER_PORT',5000)))

@cli.command()
@click.option('--recreate', default = True)
def drop_db(recreate):
    with app.app_context():
        wflowdb.db.drop_all()
        if recreate:
            wflowdb.db.create_all()


if __name__ == '__main__':
    cli()
