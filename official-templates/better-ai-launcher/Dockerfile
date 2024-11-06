# lutzapps - use the specified CUDA version
ARG BASE_IMAGE
FROM ${BASE_IMAGE:-madiator2011/better-base:cuda12.4} AS base

# lutzapps - pass the build-arg into the docker ENV as reference
# as BASE_IMAGE is in "global scope" of the Dockerfile, it need to be "consumed" to be available in this stage
ARG BASE_IMAGE
ENV BASE_IMAGE=$BASE_IMAGE

#FROM madiator2011/better-base:cuda12.4 AS base

# lutzapps - prepare for local developement and debugging
# needed to change the ORDER of "apt-get commands" and move the "update-alternatives" for python3
# AFTER the "apt-get remove -y python3.10" cmd, OTHERWISE the symlink to python3
# is broken in the image and the VSCode debugger could not exec "python3" as CMD overwrite

# Install Python 3.11, set it as default, and remove Python 3.10
RUN apt-get update && \
    # removed: 2x git nginx ffmpeg (as they are already installed with the base image)
    # added: pigz (for parallel execution of TAR files); zip (for easier folder compression)
    apt-get install -y python3.11 python3.11-venv python3.11-dev python3.11-distutils \
    aria2 pigz zip pv rsync zstd libtcmalloc-minimal4 bc && \
    apt-get remove -y python3.10 python3.10-minimal libpython3.10-minimal libpython3.10-stdlib && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install pip for Python 3.11
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python3.11 get-pip.py && \
    rm get-pip.py

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the Python dependencies (as "managed pip")
RUN python3.11 -mpip install --no-cache-dir -r requirements.txt

# Copy the application code
# lutzapps - only copy the "app" folder and not the root (".") to avoid cluttering the docker container with src-files
COPY app .

# Install File Browser
RUN curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

# Set environment variables for developent/production
# overwrite this ENV in "tasks.json" docker run "env" section or overwrite in your ".env" file to "development"
ENV FLASK_ENV=production

# gevent monkey-patching is being used, enable gevent support in the debugger with GEVENT_SUPPORT=True
# add this ENV in "tasks.json" docker run "env" section or populate in your ".env" file
# ENV GEVENT_SUPPORT=True

# lutzapps - keep Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV APP_PATH=/app/app.py

# Expose the port Nginx will listen on
EXPOSE 7222

# lutzapps - moved the 4 static assets (3x PNG, 1x MP3) into the /app/static" folder for cleaner view
# lutzapps - added a "app/tests" folder with script and testdata and readme file
# lutzapps - grouped NGINX files in a sub-folder for cleaner view

# NGINX configuration
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/readme.html /usr/share/nginx/html/readme.html

# Copy all necessary scripts
COPY --from=scripts start.sh /
# --from=scripts is defined as a "shared" location in "docker-bake.hcl" in the "contexts" dict:
#   scripts = "../../container-template"
# the local "start.sh" is (intentionally) empty
# to build all from *one* location, copy "start.sh" here into the project workspace folder first
# cp ../../container-template/scripts/start.sh start.sh
#COPY start.sh /

COPY pre_start.sh /
# lutzapps - add execution flags to added "/app/tests/populate_testdata.sh"
RUN chmod +x /pre_start.sh /start.sh /app/tests/populate_testdata.sh

# Copy the download_venv.sh script and make it executable
COPY download_venv.sh /app/download_venv.sh
RUN chmod +x /app/download_venv.sh

# CMD
# During debugging, this entry point will be overridden as "python3".
# For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["/start.sh"]