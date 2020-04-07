FROM ubuntu:focal

# Install required system packages for our CronJob
RUN apt-get update && apt-get install --yes --no-install-recommends python3-pip python3-setuptools python3-dev python3-wheel

ADD . .
RUN pip3 install --no-cache-dir -r requirements.txt

ENTRYPOINT python3 poller.py
