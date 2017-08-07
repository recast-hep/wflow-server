import logging
import redis
import os
import celery.result
from wflowcelery.fromenvapp import app
def wflow_job_db():
   return redis.StrictRedis(
                host = os.environ['WFLOW_CELERY_REDIS_HOST'],
                db   = os.environ['WFLOW_CELERY_REDIS_DB'],
                port = os.environ['WFLOW_CELERY_REDIS_PORT'],
          ) 

log = logging.getLogger(__name__)
db = wflow_job_db()

######### Generic Job DB stuff
#########

def celery_id(jobguid):
    return db.get('wflowdb:{}:celery'.format(jobguid))

def register_job(jobguid,celeryid):
    db.rpush('wflowdb:workflow_jobs',jobguid)
    db.set('wflowdb:{}:celery'.format(jobguid),celeryid)

def all_jobs():
    return db.lrange('wflowdb:workflow_jobs',0,-1)

def job_details(jobguid):
    return jobs_details([jobguid])

def jobs_details(jobguids):
    status     = job_status(jobguids)
    details = {jobid: {
        'job_type': 'workflow',
        'status': status
        } for jobid,status in zip(jobguids,status)
    }
    return details

def job_status(jobguid):
    return celery.result.AsyncResult(celery_id(jobguid)).state