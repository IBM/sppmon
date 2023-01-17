# NOTE: Run this from the project root directory
FROM python:3.10

WORKDIR /usr/src/app

COPY ./python/spmon_requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "python", "./python/spmon.py", \
     "--cfg", "/spmon/spconnections.conf", \
     "--queries", "/spmon/spqueries.json"]