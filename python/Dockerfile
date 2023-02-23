FROM python:3.10

ARG PIP_INDEX_URL

# Apply OS & python updates
USER root
RUN (yum -y check-update || { rc=$?; [ "$rc" -eq 100 ] && exit 0; exit "$rc"; }) && yum -y upgrade
RUN python3 -m pip install --upgrade pip

# Create defaultUser in new group defaultGroup
RUN groupadd -r defaultGroup && useradd --no-log-init -r -g defaultGroup defaultUser

WORKDIR /usr/src/app

# change ownership of copied files, if neccessary:
#   COPY --chown=<username>:<groupname> <sourcefolder> <targetfolder>

# safer option, as defaultUser has only read permissions
#COPY --chown=root:root . .
# less safe option, as owner also has write permissions
COPY --chown=defaultUser:defaultGroup . .
# Addon to the previous command:
# Only uncomment if files/dir needs to be created in the working dir
RUN chown defaultUser:defaultGroup /usr/src/app
# (non-recursive, only workdir, as copy does already others)

RUN pip install --no-cache-dir -r requirements.txt

# Change to defaultUser
USER defaultUser

ENTRYPOINT [ "python" ]

CMD [ "./sppmon.py" ]