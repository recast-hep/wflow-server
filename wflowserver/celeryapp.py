import os
import logging
from celery import Celery

log = logging.getLogger(__name__)
app = Celery()

app.conf.broker_url = os.environ.get('WFLOW_BEAT_BROKER','redis://localhost:6379/0')

app.conf.beat_schedule = {
    'periodic-deployer': {
        'task': 'celeryapp.deployer',
        'schedule': 1.0,
		'options': {
			'queue': 'private_queue'
		}
    },
    'periodic-reaper': {
        'task': 'celeryapp.reaper',
        'schedule': 30.0,
		'options': {
			'queue': 'private_queue'
		}
    },
    'periodic-state-updater': {
        'task': 'celeryapp.state_updater',
        'schedule': 10.0,
		'options': {
			'queue': 'private_queue'
		}
    }
}

import wflowserver.server
import wflowserver.wflowdb as wdb
from sqlalchemy import or_

@app.task
def deployer():
    '''
    take all registered workflows and actually creates workflow
    deployments for them.

    We limit the number of active deployment slots to WFLOW_NSLOTS
    '''

    WFLOW_NSLOTS = int(os.environ.get('WFLOW_NSLOTS','2'))
    with wflowserver.server.app.app_context():
        all_active_started = wflowdb.Workflow.query.filter(
            or_(wflowdb.Workflow.state==wflowdb.WorkflowState.STARTED,
                wflowdb.Workflow.state==wflowdb.WorkflowState.ACTIVE
        )).all()
        all_active_started = len(all_active_started)

        n_openslots = WFLOW_NSLOTS - all_active_started
        if n_openslots > 0:
            log.info('got %s open workflow slots so we could be submitting. currently registered workflows %s', n_openslots ,all_registered)
            for wflow in all_registered[:n_openslots]:
                log.info('working on wflow %s', wflow)
                # from wflowcelery.fromenvapp import app as backendapp
                # import wflowcelery.backendtasks
                # backendapp.set_current()
                # log.info('submitting to celery (backend version) %s', backendapp.broker_connection())
                # result = wflowcelery.backendtasks.run_analysis.apply_async(
                #     ('setupFromURL','generic_onsuccess','cleanup',wflow.wflow_id),
                #     queue = wflow.queue)
                # log.info('celery id is: %s', result.id)
                # wflow.celery_id = result.id

                try:
                    from kubernetes import config, client
                    config.load_incluster_config()
                    import yaml
                    wflowname = 'wflow-{}'.format(wflow.wflow_id)
                    spec = yaml.load(open('/yadage_job/job_template'))
                    spec['metadata']['name'] = wflowname
                    spec['spec']['template']['metadata']['name'] = wflowname

                    cmd = spec['spec']['template']['spec']['containers'][0]['command'][-1]
                    cmd = cmd.format(wflowid = wflow.wflow_id)
                    spec['spec']['template']['spec']['containers'][0]['command'][-1] = cmd

                    j = client.BatchV1Api().create_namespaced_job('default',spec)
                    wflow.state = wdb.WorkflowState.STARTED
                except:
                    log.exception()

                # app.set_current()
                log.info('submitted registered workflow %s as celery id %s'.format(wflow.wflow_id, wflow.celery_id))
                wdb.db.session.add(wflow)
            log.info('about to commit to session')
            wdb.db.session.commit()
        else:
            log.info('no open slots available -- please stand by...')

@app.task
def state_updater():
    '''
    periodically checks state of active deployments and updates the deployment
    database.

    Right now this is a celery task -- but will be a Kubernetes Deployment/Object soon.
    '''
    with wflowserver.server.app.app_context():
        all_active_started = wflowdb.Workflow.query.filter(
            or_(wflowdb.Workflow.state==wflowdb.WorkflowState.STARTED,
                wflowdb.Workflow.state==wflowdb.WorkflowState.ACTIVE
        )).all()
        for wflow in all_active_started:
            try:
                from kubernetes import config, client
                config.load_incluster_config()
                wflowname = 'wflow-{}'.format(wflow.wflow_id)
                j = client.BatchV1Api().read_namespaced_job(wflowname,'default')
                print(j.status)

                if j.status.failed:
                    wflow.state = wdb.WorkflowState.FAILURE
                if j.status.succeeded:
                    wflow.state = wdb.WorkflowState.SUCCESS
                if j.status.active:
                    wflow.state = wdb.WorkflowState.ACTIVE
                if wflow.state.value in ['FAILURE','SUCCESS']:
                    log.info('deleting job %s', wflowname)
                    client.BatchV1Api().delete_namespaced_job(wflowname,'default',j.spec, propagation_policy = 'Background')
                    client.CoreV1Api().delete_collection_namespaced_pod('default',label_selector = 'job-name={}'.format(wflowname))
            except:
                log.exception()
            # if not wflow.celery_id: continue
            # from wflowcelery.fromenvapp import app as backendapp
            # import celery.result
            # log.info('checking result (backend version) %s', backendapp.broker_connection())
            # celery_state = celery.result.AsyncResult(wflow.celery_id, app = backendapp).state
            # log.info('celery state %s', celery_state)
            # wflow.state = getattr(wdb.WorkflowState,celery_state)
            # log.info('updated state for workflow %s is %s', wflow.wflow_id, wflow.state.value)
            wdb.db.session.add(wflow)
        wdb.db.session.commit()
    log.info('all states updated')

@app.task
def reaper():
    '''
    kills workflows that seem stuck or otherwise hopeless
    '''
    log.info('we will reap the dead workflows')
    pass
