import copy
import logging

log = logging.getLogger(__name__)

entrypoint_map = {
    'yadage': 'wflowyadageworker.backendtasks:run_workflow'
}

def entrypoint(wflowtype):
    return entrypoint_map[wflowtype]


def request_to_context(request, jobguid):
    log.info('assigned jobguid {} to workflow request {}'.format(jobguid,request))

    context = copy.deepcopy(request)
    context['jobguid'] = jobguid
    wflowtype = context.pop('wflowtype')
    context['entry_point'] = entrypoint(wflowtype)
    return context
