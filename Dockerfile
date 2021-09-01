FROM python:3.9

# For a smaller container use the following instead
#FROM python:3.8-slim

WORKDIR /usr/src/app

COPY ./python/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

# Python Code
COPY ./python ./python

# Config files
#COPY ./config_files ./config_files

# scripts
COPY ./scripts/addConfigFile.py ./scripts/addConfigFile.py
COPY ./scripts/utils.py ./scripts/utils.py

ENTRYPOINT [ "python", "./python/sppmon.py" ]