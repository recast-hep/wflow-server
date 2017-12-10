import logging
import redis
import os
import celery.result
from wflowcelery.fromenvapp import app
import enum
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class WorkflowState(enum.Enum):
    REGISTERED = "REGISTERED"
    STARTED    = "STARTED"
    ACTIVE     = "ACTIVE"
    FAILURE    = "FAILURE"
    SUCCESS    = "SUCCESS"

class Workflow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wflow_id  = db.Column(db.String(36), unique=True, nullable=False)
    context   = db.Column(db.JSON())
    state     = db.Column(db.Enum(WorkflowState))

    queue     = db.Column(db.String(20))
    celery_id  = db.Column(db.String(36))

    def __repr__(self):
        return '<Workflow %r>' % self.wflow_id

def register_wflow(context,queue):
    wflow = Workflow(
        wflow_id = context['jobguid'],
        context = context,
        queue = queue,
        state = WorkflowState.REGISTERED
    )
    db.session.add(wflow)
    db.session.commit()

def all_wflows():
    return [w.wflow_id for w in Workflow.query.all()]

def wflow_config(wflowguid):
    wflow = Workflow.query.filter_by(wflow_id=wflowguid).first()
    if not wflow:
        raise RuntimeError('wflow not found for id %s %s', wflowguid, Workflow.query.all())
    return wflow.context

def wflow_status(wflowguid):
    wflow = Workflow.query.filter_by(wflow_id=wflowguid).first()
    if not wflow:
        raise RuntimeError('wflow not found for id %s %s', wflowguid, Workflow.query.all())
    return wflow.state.value
