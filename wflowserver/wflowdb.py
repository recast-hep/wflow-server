import logging
import redis
import os
import celery.result
from wflowcelery.fromenvapp import app

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Workflow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wflow_id  = db.Column(db.String(36), unique=True, nullable=False)
    celery_id = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return '<Workflow %r>' % self.wflow_id

def register_wflow(wflowguid,celeryid):
    wflow = Workflow(wflow_id = wflowguid, celery_id = celeryid)
    db.session.add(wflow)
    db.session.commit()

def all_wflows():
    return [w.wflow_id for w in Workflow.query.all()]

def wflow_status(wflowguid):
    wflow = Workflow.query.filter_by(wflow_id=wflowguid).first()
    return celery.result.AsyncResult(wflow.celery_id).state
