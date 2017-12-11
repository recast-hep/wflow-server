from setuptools import setup, find_packages

setup(
  name = 'wflow-server',
  version = '0.0.1',
  description = 'workflow server for RECAST and other workflow-based services',
  author = 'Lukas Heinrich',
  author_email = 'lukas.heinrich@cern.ch',
  packages=find_packages(),
  install_requires = [
    'celery',
    'wflow-backend',
    'pyyaml',
    'Flask',
    'Flask-SQLAlchemy',
    'psycopg2',
    'kubernetes'
  ],
  entry_points = {
  },
  include_package_data = True,
  zip_safe=False
)
