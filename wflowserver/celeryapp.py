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

@app.task
def deployer():
    '''
    take all registered workflows and actually creates workflow
    deployments for them.

    We limit the number of active deployment slots to WFLOW_NSLOTS
    '''

    WFLOW_NSLOTS = int(os.environ.get('WFLOW_NSLOTS','2'))

    with wflowserver.server.app.app_context():
        all_started = len(wdb.Workflow.query.filter_by(state = wdb.WorkflowState.STARTED).all())
        all_registered =  wdb.Workflow.query.filter_by(state = wdb.WorkflowState.REGISTERED).all()

        n_openslots = WFLOW_NSLOTS - all_started
        if n_openslots > 0:
            log.info('got %s open workflow slots so we could be submitting. currently registered workflows %s', n_openslots ,all_registered)
            for wflow in all_registered[:n_openslots]:
                log.info('working on wflow %s', wflow)
                from wflowcelery.fromenvapp import app as backendapp
                import wflowcelery.backendtasks
                backendapp.set_current()
                log.info('submitting to celery (backend version) %s', backendapp.broker_connection())
                result = wflowcelery.backendtasks.run_analysis.apply_async(
                    ('setupFromURL','generic_onsuccess','cleanup',wflow.context),
                    queue = wflow.queue)
                log.info('celery id is: %s', result.id)
                wflow.celery_id = result.id
                wflow.state = wdb.WorkflowState.STARTED
                app.set_current()
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
        all_started =  wdb.Workflow.query.all()
        for wflow in all_started:
            if not wflow.celery_id: continue
            from wflowcelery.fromenvapp import app as backendapp
            import celery.result
            log.info('checking result (backend version) %s', backendapp.broker_connection())
            celery_state = celery.result.AsyncResult(wflow.celery_id, app = backendapp).state
            log.info('celery state %s', celery_state)
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
