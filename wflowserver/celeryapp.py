import os
import logging
import requests
from celery import Celery
import wflowserver.server
import wflowserver.wflowdb as wdb
from sqlalchemy import or_
import yaml
from kubernetes import config, client
config.load_incluster_config()

log = logging.getLogger(__name__)
app = Celery()

app.conf.broker_url = os.environ.get('WFLOW_BEAT_BROKER','redis://localhost:6379/0')

app.conf.beat_schedule = {
    'periodic-deployer': {
        'task': 'celeryapp.deployer',
        'schedule': 10.0,
		'options': {
			'queue': 'private_queue'
		}
    },
    'periodic-reaper': {
        'task': 'celeryapp.reaper',
        'schedule': 60.0,
		'options': {
			'queue': 'private_queue'
		}
    },
    'periodic-state-updater': {
        'task': 'celeryapp.state_updater',
        'schedule': 20.0,
		'options': {
			'queue': 'private_queue'
		}
    }
}


def deploy_noninteractive(wflowid):
    wflowname = 'wflow-nonint-{}'.format(wflowid)
    spec = yaml.load(open('/yadage_job/job_template'))
    spec['metadata']['name'] = wflowname
    spec['spec']['template']['metadata']['name'] = wflowname

    cmd = spec['spec']['template']['spec']['containers'][0]['command'][-1]
    cmd = cmd.format(wflowid = wflowid)
    spec['spec']['template']['spec']['containers'][0]['command'][-1] = cmd

    j = client.BatchV1Api().create_namespaced_job('default',spec)
    return j, None

def status_noninteractive(wflowid):
    wflowname = 'wflow-nonint-{}'.format(wflowid)
    j = client.BatchV1Api().read_namespaced_job(wflowname,'default')
    return {
        'ready': j.status.failed or j.status.succeeded,
        'success': j.status.succeeded and not j.status.failed,
        'active': True if j.status.active else False
    }

def delete_noninteractive(wflowid):
    wflowname = 'wflow-nonint-{}'.format(wflowid)
    log.info('deleting job %s', wflowname)
    client.BatchV1Api().delete_namespaced_job(wflowname,'default',{}, propagation_policy = 'Background')
    client.CoreV1Api().delete_collection_namespaced_pod('default', label_selector = 'job-name={}'.format(wflowname))


def deploy_interactive(wflowid):
    wflowname = 'wflow-int-{}'.format(wflowid)
    deployment, service = yaml.load_all(open('/yadage_job/int_template'))
    deployment['metadata']['name'] = wflowname
    deployment['spec']['template']['metadata']['labels']['app'] = wflowname


    cmd = deployment['spec']['template']['spec']['containers'][0]['command'][-1]
    cmd = cmd.format(wflowid = wflowid)
    deployment['spec']['template']['spec']['containers'][0]['command'][-1] = cmd


    service['metadata']['name'] = wflowname
    service['spec']['selector']['app'] = wflowname


    d = client.ExtensionsV1beta1Api().create_namespaced_deployment('default',deployment)
    s = client.CoreV1Api().create_namespaced_service('default',service)
    return d,s

config.load_incluster_config()
def status_interactive(wflowid):
    wflowname = 'wflow-int-{}'.format(wflowid)

    deployment_status  = client.ExtensionsV1beta1Api().read_namespaced_deployment(wflowname,'default').status
    unavailable = deployment_status.unavailable_replicas
    unavailable = 0 if unavailable is None else unavailable
    available_replicas = deployment_status.replicas - unavailable
    if available_replicas:
        status = requests.get('http://{}.default.svc.cluster.local:8080/status'.format(wflowname)).json()
        log.info('status is %s', status)
    else:
        log.info('no available replicas for %s', wflowid)
        status =  {'ready': False, 'success': False}
    return {
        'ready': status['ready'],
        'success': status['success'],
        'active': available_replicas > 0
    }

def delete_interactive(wflowid):
    wflowname = 'wflow-int-{}'.format(wflowid)
    log.info('deleting interactive deployment %s', wflowname)
    #this should be quick and synchronous... (otherwise need to wait for it in another way)
    status = requests.get('http://{}.default.svc.cluster.local:8080/finalize'.format(wflowname)).json()
    log.info('finalization status %s', status)
    client.ExtensionsV1beta1Api().delete_namespaced_deployment(wflowname,'default',{'propagation_policy': 'Foreground'})
    client.ExtensionsV1beta1Api().delete_collection_namespaced_replica_set('default', label_selector = 'app={}'.format(wflowname))
    client.CoreV1Api().delete_collection_namespaced_pod('default', label_selector = 'app={}'.format(wflowname))
    client.CoreV1Api().delete_namespaced_service(wflowname,'default')

@app.task
def deployer():
    '''
    take all registered workflows and actually creates workflow
    deployments for them.

    We limit the number of active deployment slots to WFLOW_NSLOTS
    '''

    WFLOW_NSLOTS = int(os.environ.get('WFLOW_NSLOTS','2'))
    with wflowserver.server.app.app_context():
        all_registered = wdb.Workflow.query.filter(
            wdb.Workflow.state==wdb.WorkflowState.REGISTERED,
        ).all()

        all_active_started = len(wdb.Workflow.query.filter(
            or_(wdb.Workflow.state==wdb.WorkflowState.STARTED,
                wdb.Workflow.state==wdb.WorkflowState.ACTIVE
        )).all())

        n_openslots = WFLOW_NSLOTS - all_active_started
        if n_openslots > 0:
            log.info('got %s open workflow slots so we could be submitting. currently registered workflows %s', n_openslots ,all_registered)
            for wflow in all_registered[:n_openslots]:
                log.info('working on wflow %s %s', wflow, wflow.context)
                try:
                    if not wflow.context['interactive']:
                        log.info('starting non-interactive deployment')
                        job,_ = deploy_noninteractive(wflow.wflow_id)
                        wflow.state = wdb.WorkflowState.STARTED
                    else:
                        log.info('starting interactive deployment')
                        deployment, service = deploy_interactive(wflow.wflow_id)
                        wflow.state = wdb.WorkflowState.STARTED
                    log.info('about to commit to session')
                    wdb.db.session.add(wflow)
                    wdb.db.session.commit()
                except:
                    log.exception('api acces failed')
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
        all_active_started = wdb.Workflow.query.filter(
            or_(wdb.Workflow.state==wdb.WorkflowState.STARTED,
                wdb.Workflow.state==wdb.WorkflowState.ACTIVE
        )).all()
        log.info('checking %s active or started workflows', len(all_active_started))
        for wflow in all_active_started:
            try:
                log.info('checking wflow status for %s', wflow.wflow_id)

                if not wflow.context['interactive']:
                    status = status_noninteractive(wflow.wflow_id)
                else:
                    status = status_interactive(wflow.wflow_id)

                if status['ready']:
                    if status['success']:
                        wflow.state = wdb.WorkflowState.SUCCESS
                    else:
                        wflow.state = wdb.WorkflowState.FAILURE
                elif status['active']:
                    wflow.state = wdb.WorkflowState.ACTIVE

                if wflow.state.value in ['FAILURE','SUCCESS']:
                    pass
                    log.info('would delete but not deleting')
                    if not wflow.context['interactive']:
                        delete_noninteractive(wflow.wflow_id)
                    else:
                        delete_interactive(wflow.wflow_id)
                wdb.db.session.add(wflow)
                wdb.db.session.commit()
            except:
                log.exception('api access failed')
    log.info('all states updated')

@app.task
def reaper():
    '''
    kills workflows that seem stuck or otherwise hopeless
    '''
    log.info('we will reap the dead workflows')
    pass
