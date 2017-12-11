FROM python:3
ARG WFLOW_BACKEND_TAG=master
RUN pip install https://github.com/recast-hep/wflow-backend/archive/${WFLOW_BACKEND_TAG}.zip --process-dependency-links
ADD . /code
WORKDIR /code
RUN pip install --process-dependency-links .
