# lutzapps - use the specified CUDA version
ARG BASE_IMAGE
FROM ${BASE_IMAGE:-madiator2011/better-base:cuda12.4} AS base

# lutzapps - pass the build-arg into the docker ENV as reference
# as BASE_IMAGE is in "global scope" of the Dockerfile, it need to be "consumed" to be available in this stage
ARG BASE_IMAGE
ENV BASE_IMAGE=$BASE_IMAGE

# lutzapps - replaced by above bake build-args
#FROM madiator2011/better-base:cuda12.4 AS base

# lutzapps - prepare for local developement and debugging
# needed to change the ORDER of "apt-get commands" and move the "update-alternatives" for python3
# AFTER the "apt-get remove -y python3.10" cmd, OTHERWISE the symlink to python3
# is broken in the image and the VSCode debugger could not exec "python3" as CMD overwrite
# also fixed a boring "Blinker" blocking error

RUN apt-get update && \
    ### ---> needed Tools for Installer
    # removed: 2x git nginx ffmpeg (as they are already installed with the base image)
    # added: pigz (for parallel execution of TAR files); zip (for easier folder compression)
    apt-get install -y aria2 pigz zip pv rsync zstd tree libtcmalloc-minimal4 bc \
    # add Python3.11 as system Python version, serving the Python Flask App
    python3.11 python3.11-venv python3.11-dev python3.11-distutils && \
    # not remove Python3.10, as we need it for "official" app support (e.g. for kohya_ss VENV)
    ###apt-get remove -y python3.10 python3.10-minimal libpython3.10-minimal libpython3.10-stdlib && \
    #
    # setup an "alias" for "python" be symlinked to Python3.11
    # (which is the default anyway after this installation here of Python 3.11)
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    #
    # setup the "python3" alias for Python3.11, as this is what the debugger needs (not work with 3.10)
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    #
    # VENV will have their own "preferred/supported/recommended" Python version, as e.g.
    # the "kohya_ss" app, only supports Python up to version 3.10 (but not 3.11)
    #
    # until here we have a broken "Blinker" installation from some base images before,
    # and if we try to "update" "Blinker" for Python3.10 or via e.g. "pip install --upgrade blinker",
    # or "pip install blinker==x.y.z.z", this breaks, as it was installed in an APT bundle,
    # which can not be safely upgraded (= Uninstall/Reinstall)! It breaks as follows:
    # we get a blinker 1.4 uninstall error chained by trying to uninstall "distutils":
    #    8.568     Found existing installation: blinker 1.4
    #    8.782 error: uninstall-distutils-installed-package
    #    8.782 
    #    8.782 × Cannot uninstall blinker 1.4
    #    8.782 ╰─> It is a distutils installed project and thus we cannot accurately determine which files belong to it which would lead to only a partial uninstall.
    # that not only blocks building the docker image, but later also breaks the "kohya_ss" app during setup,
    # which try to install Blinker and Python310-venv from "setup-runpod.sh":
    #   # Install tk and python3.10-venv
    #   echo "Installing tk and python3.10-venv..."
    #   apt update -y && apt install -y python3-tk python3.10-venv
    #
    # Python 3.10 needs to run as Kohya's "official" requirement, and is used in the VENV
    #
    # first uninstall the APT bundle package for "Blinker"
    apt-get remove -y python3-blinker && \
    # then re-install the APT unbundled package of "Blinker back",
    # together with Python3.10 venv, which we need to setup the kohya_ss VENV
    apt-get install -y python3-tk python3.10-venv && \
    # this re-captures back the "python3" alias for Python3.10, but not the "python" alias (stays for Python3.11)
    # the "Python3.11" and "Python3.10" cmds work too
    # global PIP is 3.11, VENV pip is 3.10
    #
    # ---> CUDA 12.4 Toolkit (is already in the 12.4 base-image)
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb && \
    dpkg -i cuda-keyring_1.1-1_all.deb && \
    ### need to refresh the repository metatdata, after downloading this NVIDIA downloaded package list!!!
    apt-get update && \
    apt-get -y install cuda-toolkit-12-4 && \
    #
    # ---> get the latest cuDNN 9.x version supporting CUDA 12.x
    # remove the current dev package which depends on libcudnn9-cuda-12 and breaks the upgrade otherwise
    apt-get remove -y --allow-change-held-packages libcudnn9-cuda-12 libcudnn9-dev-cuda-12 && \
    apt-get -y --allow-change-held-packages install cudnn-cuda-12 && \
    #
    # clean-up resources and caches
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install pip for Python 3.11
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python3.11 get-pip.py && \
    rm get-pip.py

# set the default python_cmd (and version) for the apps 'ba1111' and 'bforge' default launch script 'webui.sh'
ENV python_cmd=python3.11

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
# ENV vars alternatively could also stay in two different Dockerfiles: 'Dockerfile-Prod' and 'Dockerfile-Dev')

### PROD START:
#
# ENV APP_CONFIGS_MANIFEST_URL=https://better.s3.madiator.com/app_configs.json
#
# overwrite this ENV in "tasks.json" docker run "env" section, docker-compose-debug.yml, or overwrite in your ".env" file to "development"
ENV FLASK_ENV=production
#
### PROD END

### DEV START:
#
ENV APP_CONFIGS_MANIFEST_URL=https://better-dev.s3.madiator.com/app_configs.json
#
# alternativly add the following ENV vars in "tasks.json" docker run "env" section, docker-compose-debug.yml,
# or populate them in in your ".env" file, instead of setting them here in the Dockerfile
#
# gevent monkey-patching is being used, enable gevent support in the debugger with GEVENT_SUPPORT=True
# ENV GEVENT_SUPPORT=True
#
# keep Python from generating .pyc files in the container
# this should however be removed for production as it disables bytecode caching
# ENV PYTHONDONTWRITEBYTECODE=1
#
### DEV END


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

# HELP configuration ('/static/' is configured be hosting '/app/static/' content in nginx.conf)
COPY README.md /app/static/README.md
COPY README-Development.txt /app/static/README-Development.txt
COPY app/tests/README-SHARED_MODELS.txt /app/static/README-SHARED_MODELS.txt


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