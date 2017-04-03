FROM python:2.7
ADD . /code
WORKDIR /code
RUN echo bustit
RUN pip install --process-dependency-links .
