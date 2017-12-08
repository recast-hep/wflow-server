import os
import logging
from celery import Celery

log = logging.getLogger(__name__)
app = Celery()

app.conf.broker_url = 'redis://{}:{}/{}'.format(
    os.environ.get('WFLOW_BEAT_REDIS_HOST','localhost')
    os.environ.get('WFLOW_BEAT_REDIS_PORT','6379')
    os.environ.get('WFLOW_BEAT_REDIS_DB','0')
)

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
        'schedule': 10.0,
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

@app.task
def deployer():
    '''
    take all registered workflows and actually creates workflow
    deployments for them.

    We limit the number of active deployment slots to WFLOW_NSLOTS
    '''

    WFLOW_NSLOTS = int(os.environ.get('WFLOW_NSLOTS','2'))

    import wflowcelery.backendtasks
    from wflowcelery.fromenvapp import app as backendapp
    backendapp.set_current()
    with wflowserver.server.app.app_context():
        all_started = len(wdb.Workflow.query.filter_by(state = wdb.WorkflowState.STARTED).all())

        n_openslots = WFLOW_NSLOTS - all_started
        if n_openslots > 0:
            log.info('got %s open workflow slots so we could be submitting', n_openslots)
            all_registered =  wdb.Workflow.query.filter_by(state = wdb.WorkflowState.REGISTERED).all()
            for wflow in all_registered[:n_openslots]:

                result = wflowcelery.backendtasks.run_analysis.apply_async(
                    ('setupFromURL','generic_onsuccess','cleanup',wflow.context),
                    queue = wflow.queue)
                wflow.celery_id = result.id
                wflow.state = wdb.WorkflowState.STARTED
                log.info('submitted registered workflow %s as celery id %s'.format(wflow.wflow_id, wflow.celery_id))
                wdb.db.session.add(wflow)
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
    import wflowcelery.backendtasks
    from wflowcelery.fromenvapp import app as backendapp
    import celery.result
    backendapp.set_current()
    with wflowserver.server.app.app_context():
        all_started =  wdb.Workflow.query.filter_by(state = wdb.WorkflowState.STARTED).all()
        for wflow in all_started:
            celery_state = celery.result.AsyncResult(wflow.celery_id).state
            wflow.state = getattr(wdb.WorkflowState,celery_state)
            log.info('updated state for workflow %s is %s', wflow.wflow_id, wflow.state.value)
            wdb.db.session.add(wflow)
        wdb.db.session.commit()
    log.info('all states updated')

@app.task
def reaper():
    '''
    kills workflows that seem stuck or otherwise hopeless
    '''
    print 'we will reap the dead workflows'
    pass
