FROM python:3
RUN pip install \
    pytz billiard vine amqp kombu celery Werkzeug itsdangerous \
    click MarkupSafe Jinja2 Flask SQLAlchemy Flask-SQLAlchemy psycopg2 \
    rsa cachetools pyasn1-modules google-auth websocket-client ipaddress oauthlib \
    requests-oauthlib python-dateutil kubernetes pycparser cffi asn1crypto \
    cryptography pynacl bcrypt paramiko redis scp glob2
ARG WFLOW_BACKEND_TAG=master
RUN pip install https://github.com/recast-hep/wflow-backend/archive/${WFLOW_BACKEND_TAG}.zip --process-dependency-links
ADD . /code
WORKDIR /code
RUN pip install --process-dependency-links .
