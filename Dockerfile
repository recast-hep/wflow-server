FROM python:3
ARG WFLOWCELERYTAG=master
RUN echo bustit
RUN pip install https://github.com/recast-hep/wflow-celery/archive/${WFLOWCELERYTAG}.zip --process-dependency-links
ADD . /code
WORKDIR /code
RUN pip install --process-dependency-links .
