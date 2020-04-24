FROM ubuntu:18.04

RUN apt-get update \
  && apt-get install -y python3-pip python3-dev libcurl4-openssl-dev libssl-dev \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip

## Create a virtualenv for dependencies. This isolates these packages from
## system-level packages.
## Use -p python3 or -p python3.7 to select python version. Default is version 2.
#RUN virtualenv /venv -p python3.7
#
## Setting these environment variables are the same as running
## source /env/bin/activate.
#ENV VIRTUAL_ENV /venv
#ENV PATH /venv/bin:$PATH

# Copy the application's requirements.txt and run pip to install all
# dependencies into the virtualenv.
RUN pip3 install requests
RUN pip3 install flask
RUN pip3 install flask_cors
RUN pip3 install gunicorn
RUN pip3 install google-cloud-secret-manager
RUN pip3 install firebase_admin
RUN pip3 install mock
RUN pip3 install google-auth
RUN pip3 install google-cloud-firestore
#ADD requirements.txt /app/requirements.txt
#RUN pip3 install -r /app/requirements.txt

# Add the application source code.
ADD . /

# Run a WSGI server to serve the application. gunicorn must be declared as
# a dependency in requirements.txt.
CMD gunicorn -b :$PORT main:app