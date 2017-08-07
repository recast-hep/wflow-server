import logging
import redis
import os
import celery.result
from wflowcelery.fromenvapp import app

def wflow_db():
   return redis.StrictRedis(
                host = os.environ['WFLOW_CELERY_REDIS_HOST'],
                db   = os.environ['WFLOW_CELERY_REDIS_DB'],
                port = os.environ['WFLOW_CELERY_REDIS_PORT'],
          ) 

log = logging.getLogger(__name__)
db = wflow_db()

def celery_id(wflowguid):
    return db.get('wflowdb:{}:celery'.format(wflowguid))

def register_wflow(wflowguid,celeryid):
    db.rpush('wflowdb:workflow_guids',wflowguid)
    db.set('wflowdb:{}:celery'.format(wflowguid),celeryid)

def all_wflows():
    return db.lrange('wflowdb:workflow_guids',0,-1)

def wflow_status(wflowguid):
    return celery.result.AsyncResult(celery_id(wflowguid)).state