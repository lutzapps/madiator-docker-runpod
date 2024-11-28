import os
import xml.etree.ElementTree as ET
import requests
import urllib.request
import json

# this is the replacement for the XML manifest, and defines all app_configs in full detail

# this will now be passed in from an ENV var 'APP_CONFIGS_MANIFEST_URL=xxx' set in the 'Dockerfile'
# so the Dockerfile controls between 'production' and 'development' MANIFEST_URLs and S3 download locations for the VENVS
#APP_CONFIGS_MANIFEST_URL = "https://better.s3.madiator.com/app_configs.json" # production MANIFEST_URL
#APP_CONFIGS_MANIFEST_URL = "https://better-dev.s3.madiator.com/app_configs.json" # development MANIFEST_URL
APP_CONFIGS_MANIFEST_URL = ""

# If this JSON file can not be downloaded from the MANIFEST_URL, the below code defaults apply
# This 'app_configs' dict can also be generated from code when at least one of following
# 2 ENV vars are found with following values:
#
# 1.    LOCAL_DEBUG = 'True' # this ENV var should not be passed when in the RUNPOD environment,
#       as it disabled the CF proxy Urls of the App-Manager
#       This ENV var also controls some other (debugging) aspects of the app.
#
# 2.    APP_CONFIGS_FILE = 'True' # only exists for this one purpose, to generate the below 'app_configs' dict
#       as file "/workspace/app_configs.json", which then can be uploaded to the above defined APP_CONFIGS_MANIFEST_URL


COMMON_SETTINGS = {} # this is a global dict for "common_settings" loaded from below app_configs "common_settings" during init_app_configs()

# the 'common_settings' sub dict of app_configs will be stored in above COMMON_SETTINGS GLOBAL module dict var, and then removed from app_config, as this is not an app
app_configs = {
    'common_settings': { # this 'common_settings' dictionary is transferrred to COMMON_SETTINGS global dict
        # during init_app_configs() and can be overwritten individally with DEBUG_SETTINGS['common_settings'], if non None or '' values found
        'base_download_url': '', # str: base-url used to resolve the RELATIVE download_urls of the individual VENVS
        # if app_configs['common_settings']['base_download_url'] is not explicitly set, 
        # the default is to use generate the base download url from the APP_CONFIGS_MANIFEST_URL domain
        # (production or development S3 bucket URL), so switching URL also switches VENV download locations
        # this again could be overwritten via DEBUG_SETTINGS['common_settings']['base_download_url']
        # this also can be a different base url than the APP_CONFIGS_MANIFEST_URL, so the JSON file can be on a different
        # location than the TAR VENV files. All below 'download_url' are either RELATIVE to this 'base_download_url',
        # which is the case right now, but each VENV can also define an ABSOLUTE (and different) 'download_url' for itself
        # this 'base_download_url' can also be overwitten with DEBUG_SETTINGS['common_settings']['base_download_url']
        'verify_app_size': True, # bool: check APP folder sizes during Setup (can be overwritten with DEBUG_SETTINGS['common_settings']['verify_app_size'])
        'delete_unverified_app_path': False, # bool: if set to True, delete unverified APP_PATH folder from /workspace during Setup or check_app_installation() UI function,
        # if the defined 'minimum_app_size_kb' of the app does not match at minimum the result of 'du -sk' command against the installed app_path
        # can be overwritten with DEBUG_SETTINGS['common_settings']['delete_unverified_app_path']
        'verify_venv_size': True, # bool: check VENV folder sizes during Setup (can be overwritten with DEBUG_SETTINGS['common_settings']['verify_venv_size'])
        'delete_unverified_venv_path': False, # bool: if set to True, delete unverified VENV folder from /workspace during Setup or check_app_installation() UI function,
        # if the defined 'venv_uncompressed_size_kb' of the app's found 'venv_info' does not match at minimum the result of 'du -sk' command against the installed venv_path
        # can be overwritten with DEBUG_SETTINGS['common_settings']['delete_unverified_venv_path']
        'verify_tolerance_percent': 5 # percentage (int) factor the 'verify_sizes' for app_path and venv_path are allowed to vary
        # can be overwritten with DEBUG_SETTINGS['common_settings']['verify_tolerance_percent']
    },
    'bcomfy': {
        'id': 'bcomfy',
        'name': 'Better Comfy UI',
        'command': 'cd /workspace/bcomfy && . ./bin/activate && cd /workspace/ComfyUI && python main.py --listen --port 3000 --enable-cors-header',
        'port': 3000,
        'app_path': '/workspace/ComfyUI',
        'repo_url': 'https://github.com/comfyanonymous/ComfyUI.git',
        'allow_refresh': True, # allow to refresh the app
        'venv_path': '/workspace/bcomfy',
        'venv_version_default': 'latest', # use the 'latest' VENV version by default,
         # can be overwritten with 'VENV_VERSION_<app_id>' ENV var or via DEBUG_SETTINGS['select_venv_version']
        'available_venvs': [
            { # venv SETUP: pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu124 && pip install -r requirements.txt
                # install ComfyUI-Manager and Requirements
                'version': 'official',            
                'build_info': 'v1.0 - Nov 16, 2024, 18:28 GMT by lutzapps',
                'notes': 'Python 3.11 && Cuda 12.4 && Recommended torch-2.5.1+cu124-cp311-cp311-linux_x86_64 && ComfyUI-Manager && comfy CLI',
                'branch_name': '', # empty branch_name means default = 'master'
                'commit_id': '', # if set, it wins over branch_name
                'clone_recursive': False,
                'minimum_app_size_kb': 77108, # du /workspace/ComfyUI -sk (without custom_nodes)
                'download_url': 'bcomfy/bcomfy-official.tar.gz',
                'venv_uncompressed_size_kb': 5696320, # uncompressed size of "bcomfy-official.tar.gz" (in KBytes), "du /workspace/bcomfy -sk"
                'archive_size_bytes': 3099730702, # tar filesize (in Bytes), "ls bcomfy-official.tar.gz -la"
                'sha256_hash': 'dc22367fba5829eda316858f3ff148659901f26ef8079cd76676ab1025923d19' # shasum -a 256 bcomfy-official.tar.gz
            },
            { # venv SETUP: 'official' && installed all custom nodes from below list with their requirements
                'version': 'latest',            
                'build_info': 'v1.0 - Nov 16, 2024, 20:48 GMT by lutzapps',
                'notes': 'Python 3.11 && Cuda 12.4 && Recommended torch-2.5.1+cu124-cp311-cp311-linux_x86_64 && ComfyUI-Manager && comfy CLI && 12x Custom Nodes',
                'branch_name': '', # empty branch_name means default = 'master'
                'commit_id': '', # if set, it wins over branch_name
                'clone_recursive': False,
                'minimum_app_size_kb': 409828, # "du /workspace/ComfyUI -sk" (with custom_nodes)
                'download_url': 'bcomfy/bcomfy-latest.tar.gz',
                'venv_uncompressed_size_kb': 6913704, # uncompressed size of "bcomfy-latest.tar.gz" (in KBytes), "du /workspace/bcomfy -sk"
                'archive_size_bytes': 3551621652, # tar filesize (in bytes), "ls bcomfy-latest.tar.gz -la"
                'sha256_hash': 'c621884e2d016d89a2806cb9371330493f7232168afb93e2fc1440d87da0b896' # shasum -a 256 bcomfy-latest.tar.gz
            }
        ],
        'custom_nodes': [ # following custom_nodes will be git cloned and installed with "pip install -r requirements.txt" (in Testing)
            {
                'venv_version': '*', # install this node into all (*) VENV versions
                'name': 'ComfyUI-Manager (ltdrdata)', # this node is installed into ALL (*) VENV versions
                'path': 'ComfyUI-Manager',
                'repo_url': 'https://github.com/ltdrdata/ComfyUI-Manager.git',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'ComfyUI-Essentials (cubic)', # this node is installed only into the 'latest' VENV version
                'path': 'ComfyUI_essentials',
                'repo_url': 'https://github.com/cubiq/ComfyUI_essentials',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'rgthree comfy',
                'path': 'rgthree-comfy',
                'repo_url': 'https://github.com/rgthree/rgthree-comfy',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'was node-suite comfyui (WASasquatch)',
                'path': 'was-node-suite-comfyui',
                'repo_url': 'https://github.com/WASasquatch/was-node-suite-comfyui',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'comfyui controlnet-aux (Fannovel16)',
                'path': 'comfyui_controlnet_aux',
                'repo_url': 'https://github.com/Fannovel16/comfyui_controlnet_aux',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'x-flux-comfyui (XLabs-AI)',
                'path': 'x-flux-comfyui',
                'repo_url': 'https://github.com/XLabs-AI/x-flux-comfyui',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'ComfyUI-GGUF (city96)',
                'path': 'ComfyUI-GGUF',
                'repo_url': 'https://github.com/city96/ComfyUI-GGUF',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'ComfyUI-Florence2 (kijai)',
                'path': 'ComfyUI-Florence2F',
                'repo_url': 'https://github.com/kijai/ComfyUI-Florence2',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'ComfyUI KJNodes (kijai)',
                'path': 'ComfyUI-KJNodes',
                'repo_url': 'https://github.com/kijai/ComfyUI-KJNodes',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'ComfyUI UltimateSDUpscale (ssitu)',
                'path': 'ComfyUI_UltimateSDUpscale',
                'repo_url': 'https://github.com/ssitu/ComfyUI_UltimateSDUpscale',
                'install_requirements_txt': False, # NO requirements.txt file for PIP INSTALL
                'clone_recursive': True # clone this node --recursive according to README.md
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'ControlAltAI Nodes (gseth)',
                'path': 'ControlAltAI-Nodes',
                'repo_url': 'https://github.com/gseth/ControlAltAI-Nodes',
                'install_requirements_txt': False, # NO requirements.txt file for PIP INSTALL
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'ComfyUI Easy-Use (yolain)',
                'path': 'ComfyUI-Easy-Use',
                'repo_url': 'https://github.com/yolain/ComfyUI-Easy-Use',
                'install_requirements_txt': True,
                'clone_recursive': False
            },
            {
                'venv_version': 'latest', # install this node only in the 'latest' VENV, but not in the 'official' VENV
                'name': 'ComfyUI Impact-Pack (tdrdata)',
                'path': 'ComfyUI-Impact-Pack',
                'repo_url': 'https://github.com/ltdrdata/ComfyUI-Impact-Pack',
                'install_requirements_txt': True,
                'clone_recursive': False
            }
        ],
        'bash_cmds': { # bcomfy helper cmds (all command run in activated VENV, and can pass a cwd, {app_path} makro support)
            'install-requirements': 'pip install -r requirements.txt', # for installing/refreshing custom_nodes
            'install-comfy-CLI': 'pip install comfy-cli', # install comfy CLI used in 'fix-custom-nodes'
            'fix-custom_nodes': 'comfy --skip-prompt --no-enable-telemetry set-default {app_path} && comfy node restore-dependencies',
            'pip-clean-up': 'pip cache purge && py3clean {app_path}' # clean-up pip install caches and python runtime caches
        },
    },
    'bforge': {
        'id': 'bforge', # app_name
        'name': 'Better Forge',
        'command': 'cd /workspace/bforge && . ./bin/activate && cd /workspace/stable-diffusion-webui-forge && ./webui.sh -f --listen --enable-insecure-extension-access --api --port 7862',
        'port': 7862,
        'app_path': '/workspace/stable-diffusion-webui-forge',
        'repo_url': 'https://github.com/lllyasviel/stable-diffusion-webui-forge.git',
        'allow_refresh': True, # allow to refresh the app
        'venv_path': '/workspace/bforge',
        'venv_version_default': 'latest', # use the 'latest' VENV version by default,
         # can be overwritten with 'VENV_VERSION_<app_id>' ENV var or via DEBUG_SETTINGS['select_venv_version']
        'available_venvs': [
            { # venv SETUP: 'webui.sh -f can_run_as_root=1'
                'version': 'official',
                'build_info': 'v1.0 - Nov 16, 2024, 14:32 GMT by lutzapps',
                'notes': 'Python 3.11 && Cuda 12.1 && Recommended torch-2.3.1+cu121-cp311-cp311-linux_x86_64',
                'branch_name': '', # empty branch_name means default = 'master'
                'commit_id': '', # if set, it wins over branch_name
                'clone_recursive': False,
                'minimum_app_size_kb': 108860, # "du /workspace/stable-diffusion-webui-forge -sk"
                'download_url': 'bforge/bforge-official.tar.gz',
                'venv_uncompressed_size_kb': 6719164, # uncompressed size of "bforge-official.tar.gz" (in KBytes), "du /workspace/bforge -sk"
                'archive_size_bytes': 3338464965, # tar filesize (in Bytes), "ls bforge-official.tar.gz -la"
                'sha256_hash': 'e8e4d1cedd54be30c188d2a78570634b29bb7e9bb6cfa421f608c9b9813cdf7f' # shasum -a 256 bforge-official.tar.gz
            },
            { # venv SETUP: 'official' && pip install --upgrade torch torchvision xformers --index-url "https://download.pytorch.org/whl/cu124"
                'version': 'latest',
                'build_info': 'v1.0 - Nov 16, 2024, 15:22 GMT by lutzapps',
                'notes': 'Python 3.11 && Cuda 12.4 && Upgraded to torch-2.5.1+cu124-cp311-cp311-linux_x86_64 && xformers',
                'branch_name': '', # empty branch_name means default = 'master'
                'commit_id': '', # if set, it wins over branch_name
                'clone_recursive': False,
                'minimum_app_size_kb': 108116, # "du /workspace/stable-diffusion-webui-forge -sk"
                'download_url': 'bforge/bforge-latest.tar.gz',
                'venv_uncompressed_size_kb': 6941664, # uncompressed size of "bforge-latest.tar.gz" (in KBytes), "du /workspace/bforge -sk"
                'archive_size_bytes': 3567217032, # tar filesize (in bytes), "ls bforge-latest.tar.gz -la"
                'sha256_hash': '65aeae1e5ff05d16647f8ab860694845d5d2aece5683fb2a96f6af6b4bdc05cd' # shasum -a 256 bforge-latest.tar.gz
            }
        ]
    },
    'ba1111': {
        'id': 'ba1111', # app_name
        'name': 'Better A1111',
        'command': 'cd /workspace/ba1111 && . ./bin/activate && cd /workspace/stable-diffusion-webui && ./webui.sh -f --listen --enable-insecure-extension-access --api --port 7863',
        'port': 7863,
        'app_path': '/workspace/stable-diffusion-webui',
        'repo_url': 'https://github.com/AUTOMATIC1111/stable-diffusion-webui.git',
        'allow_refresh': True, # allow to refresh the app
        'venv_path': '/workspace/ba1111',
        'venv_version_default': 'latest', # use the 'latest' VENV version by default,
         # can be overwritten with 'VENV_VERSION_<app_id>' ENV var or via DEBUG_SETTINGS['select_venv_version']
        'available_venvs': [
            { # venv SETUP: 'webui.sh -f can_run_as_root=1'
                'version': 'official',
                'build_info': 'v1.0 - Nov 16, 2024, 16:30 GMT by lutzapps',
                'notes': 'Python 3.11 && Cuda 12.1 && Recommended torch-2.1.2+cu121-cp311-cp311-linux_x86_64',
                'branch_name': '', # empty branch_name means default = 'master'
                'commit_id': '', # if set, it wins over branch_name
                'clone_recursive': False,
                'minimum_app_size_kb': 42448, # "du /workspace/stable-diffusion-webui -sk"
                'download_url': 'ba1111/ba1111-official.tar.gz',
                'venv_uncompressed_size_kb': 5090008, # uncompressed size of "ba1111-official.tar.gz" (in KBytes), "du /workspace/ba1111 -sk"
                'archive_size_bytes': 2577843561, # tar filesize (in Bytes), "ls ba1111-official.tar.gz -la"
                'sha256_hash': '4e81b2ed0704e44edfb8d48fd9b3649668619b014bd9127d8a337aca01f57b53' # shasum -a 256 ba1111-official.tar.gz
            },
            { # venv SETUP: 'official' && pip install --upgrade torch torchvision xformers --index-url "https://download.pytorch.org/whl/cu124"
                'version': 'latest',
                'build_info': 'v1.0 - Nov 16, 2024, 17:03 GMT by lutzapps',
                'notes': 'Python 3.11 && Cuda 12.4 && Upgraded to torch-2.5.1+cu124-cp311-cp311-linux_x86_64 && xformers',
                'branch_name': '', # empty branch_name means default = 'master'
                'commit_id': '', # if set, it wins over branch_name
                'clone_recursive': False,
                'minimum_app_size_kb': 41628, # "du /workspace/stable-diffusion-webui -sk"
                'download_url': 'ba1111/ba1111-latest.tar.gz',
                'venv_uncompressed_size_kb': 6160684, # uncompressed size of "ba1111-latest.tar.gz" (in KBytes), "du /workspace/ba1111 -sk"
                'archive_size_bytes': 3306240911, # tar filesize (in bytes), "ls ba1111-latest.tar.gz -la"
                'sha256_hash': '759be4096bf836c6925496099cfb342e97287e7dc9a3bf92f3a38d57d30b1d7d' # shasum -a 256 ba1111-latest.tar.gz
            }
        ]
    },
    'bkohya': {
        'id': 'bkohya', # app_name
        'name': 'Better Kohya',
        'command': 'cd /workspace/bkohya && . ./bin/activate && cd /workspace/kohya_ss && python ./kohya_gui.py --headless --share --server_port 7864', # TODO!! check other ""./kohya_gui.py" cmdlines options
        'port': 7864,
        ### need to check further command settings: 
        #   python ./kohya_gui.py --inbrowser --server_port 7864
        #
        # what works for now is the gradio setup (which is also currently activated):
        #   python ./kohya_gui.py --headless --share --server_port 7864
        # creates a gradio link for 72h like e.g. https://b6365c256c395e755b.gradio.live
        #
        # the --noverify flag currently is NOT supported anymore, need to check, in the meantime disable it
        # NOTE: the --noverify switch can be inserted dynamically at runtime via DEBUG_SETTINGS['bkohya_noverify']=true
        # the idea is to make this a "run-once" option later when we have app-settings
        #
        ### for Gradio supported reverse proxy:
        # --share               -> Share the gradio UI
        # --root_path ROOT_PATH -> root_path` for Gradio to enable reverse proxy support. e.g. /kohya_ss
        # --listen LISTEN       -> IP to listen on for connections to Gradio

        # usage: kohya_gui.py [-h] [--config CONFIG] [--debug] [--listen LISTEN]
        #             [--username USERNAME] [--password PASSWORD]
        #             [--server_port SERVER_PORT] [--inbrowser] [--share]
        #             [--headless] [--language LANGUAGE] [--use-ipex]
        #             [--use-rocm] [--do_not_use_shell] [--do_not_share]
        #             [--requirements REQUIREMENTS] [--root_path ROOT_PATH]
        #             [--noverify] ???
        #
        # options:
        # -h, --help            show this help message and exit
        # --config CONFIG       Path to the toml config file for interface defaults
        # --debug               Debug on
        # --listen LISTEN       IP to listen on for connections to Gradio
        # --username USERNAME   Username for authentication
        # --password PASSWORD   Password for authentication
        # --server_port SERVER_PORT
        #                         Port to run the server listener on
        # --inbrowser           Open in browser
        # --share               Share the gradio UI
        # --headless            Is the server headless
        # --language LANGUAGE   Set custom language
        # --use-ipex            Use IPEX environment
        # --use-rocm            Use ROCm environment
        # --do_not_use_shell    Enforce not to use shell=True when running external
        #                         commands
        # --do_not_share        Do not share the gradio UI
        # --requirements REQUIREMENTS
        #                         requirements file to use for validation
        # --root_path ROOT_PATH
        #                         `root_path` for Gradio to enable reverse proxy
        #                         support. e.g. /kohya_ss
        # --noverify            Disable requirements verification
        #
        'app_path': '/workspace/kohya_ss',
        'repo_url': 'https://github.com/bmaltais/kohya_ss.git',
        'allow_refresh': True, # allow to refresh the app
        'venv_path': '/workspace/bkohya',
        'venv_version_default': 'latest', # use the 'latest' VENV version by default,
         # can be overwritten with 'VENV_VERSION_<app_id>' ENV var or via DEBUG_SETTINGS['select_venv_version']
        'available_venvs': [
            { # venv SETUP: 'setup-runpod.sh' -> kohya_gui.sh -> requirements_runpod.txt
                'version': 'latest',
                'build_info': 'v1.0 - Nov 8, 2024, 13:13 GMT by lutzapps',
                'notes': 'Python 3.10 && FLUX.1 version with torch-2.5.0+cu124 (setup-runpod.sh with requirements_runpod.txt)',
                'branch_name': 'sd3-flux.1', # make sure we use Kohya with FLUX support branch
                # this branch also uses a 'sd-scripts' HEAD branch of 'SD3', which gets automatically checked-out too
                'commit_id': '', # if set, it wins over branch_name
                'clone_recursive': True, # is recursive clone
                'minimum_app_size_kb': 59980, # "du /workspace/kohya_ss -sk"
                'download_url': 'bkohya/bkohya-latest.tar.gz',
                'venv_uncompressed_size_kb': 12175900, # uncompressed size of "bkohya-latest.tar.gz" (in KBytes), "du /workspace/bkohya -sk"
                'archive_size_bytes': 6314758227, # tar filesize (in Bytes), "ls bkohya-latest.tar.gz -la"
                'sha256_hash': '9a0c0ed5925109e82973d55e28f4914fff6728cfb7f7f028a62e2ec1a9e4f60a' # shasum -a 256 bkohya-latest.tar.gz
            }#,
            # { # there is currently no 'official' VENV for bkohya, as this is not needed
            #     'version': 'official',                    
            #     'build_info': '',
            #     'notes': '',
            #     'branch_name': '',
            #     'commit_id': '',
            #     'clone_recursive': '',
            #     'minimum_app_size_kb': '',
            #     'download_url': '',
            #     'venv_uncompressed_size_kb': 0, # uncompressed size of "bkohya-official.tar.gz" (in KBytes), "du /workspace/bkohya -sk"
            #     'archive_size_bytes': 0, # tar filesize (in bytes), "ls bkohya-official.tar.gz -la"
            #     'sha256_hash': '' # shasum -a 256 bkohya-official.tar.gz
            # }
        ],
        'bash_cmds': { # bkohya helper cmds (all command run in activated VENV, and can pass a cwd, {app_path} makro support)
            'run-tensorboard': 'tensorboard --logdir logs --bind_all --path_prefix=/tensorboard' # for running tensorboard
            # #pip install tensorboard # 2.14.1 is pre-installed, "/tensorboard/" path location is defined via 'nginx.conf'
            # TENSORBOARD_PORT ENV var (default port=6006)
            # above cmd starts like this:
            # TensorBoard 2.14.1 at http://e5c0c7143716:6006/tensorboard/ (Press CTRL+C to quit)
            # => available at http://localhost:6006/tensorboard/
        },
    }
}

def get_app_configs() -> dict:
    return app_configs

def add_app_config(app_name:str, config:dict) -> dict:
    app_configs[app_name] = config
    return app_configs # return the modified app_configs

def remove_app_config(app_name:str) -> dict:
    if app_name in app_configs:
        del app_configs[app_name]
    return app_configs # return the modified app_configs


### lutzapps section
# helper function called by init_app_install_dirs(), init_shared_model_app_map(), init_shared_models_folders() and init_debug_settings()
def write_dict_to_jsonfile(dict:dict, json_filepath:str, overwrite:bool=False) -> bool:
    # Convert the 'dict' to JSON, and write the JSON object to file 'json_filepath'

    #json_string = json.dumps(dict, indent=4, ensure_ascii=False, sort_keys=True)  
    
    try:
        if os.path.exists(json_filepath) and not overwrite:
            error_msg = f"dictionary file '{json_filepath}' already exists (and overwrite={overwrite})"
            #print(error_msg)

            return False, error_msg # failure
        
        # Write the JSON data to a file BUGBUG
        with open(json_filepath, 'w', encoding='utf-8') as output_file:
            json.dump(dict, output_file, ensure_ascii=False, indent=4, separators=(',', ': '))

    except Exception as e:
        error_msg = f"ERROR in write_dict_to_jsonfile() - loading JSON Map File '{json_filepath}'\nException: {str(e)}"
        print(error_msg)

        return False, error_msg # failure
    
    return True, "" # success

# helper function called by init_app_install_dirs(), init_shared_model_app_map(), init_shared_models_folders() and init_debug_settings()
def read_dict_from_jsonfile(json_filepath:str) -> tuple [dict, str]:
    # Read JSON file from 'json_filepath' and return it as 'dict'

    try:
        if "://" in json_filepath: # filepath is online Url containing ":" like http:// https:// ftp://
            with urllib.request.urlopen(json_filepath) as url:
                dict = json.load(url)
        elif os.path.exists(json_filepath): # local file path, e.g. "/workspace/...""
            with open(json_filepath, 'r') as input_file:
                dict = json.load(input_file)
        else:
            error_msg = f"local dictionary file '{json_filepath}' does not exist"
            print(error_msg)

            return {}, error_msg # failure

    except Exception as e:
        error_msg = f"ERROR in read_dict_from_jsonfile() - loading JSON Map File '{json_filepath}'\nException: {str(e)}"
        print(error_msg)

        return {}, error_msg # failure

    return dict, "" # success

# helper function to return a pretty formatted DICT string for human consumption (Logs, JSON)
def pretty_dict(dict:dict) -> str:
   dict_string = json.dumps(dict, ensure_ascii=False, indent=4, separators=(',', ': '))

   return dict_string

# helper function for init_app_install_dirs(), init_shared_model_app_map(), init_shared_models_folders() and init_debug_settings()
def load_global_dict_from_file(default_dict:dict, dict_filepath:str, dict_description:str, SHARED_MODELS_DIR:str="", write_file:bool=True) -> tuple[bool, dict]:
    # returns the 'dict' for 'dict_description' from 'dict_filepath'

    success = False
    return_dict = {}

    try:
        if not SHARED_MODELS_DIR == "" and not os.path.exists(SHARED_MODELS_DIR):
            print(f"\nThe SHARED_MODELS_DIR '{SHARED_MODELS_DIR}' is not found!\nCreate it by clicking the 'Create Shared Folders' button from the WebUI 'Settings' Tab\n")
            
            return False, return_dict
        
        # read from file, if filepath is online url (http:// https:// ftp://) or local filepath exists
        if "://" in dict_filepath or \
            os.path.isfile(dict_filepath) and os.path.exists(dict_filepath):
            dict_filepath_found = True
            # read the dict_description from JSON file
            print(f"\nExisting '{dict_description}' found online and read from file '{dict_filepath}'\nThe file overwrites the code defaults!")

            return_dict, error_msg = read_dict_from_jsonfile(dict_filepath)

            success = (not return_dict == {} and error_msg == "") # translate to success state

            if not success: # return_dict == {}
                dict_filepath_found = False # handle 404 errors from online urls
                return_dict = default_dict # use the code-defaults dict passed in

        else: # init the dict_description from app code
            dict_filepath_found = False
            print(f"No {dict_description}_FILE found, initializing default '{dict_description}' from code ...")
            # use already defined dict from app code
            if write_file:
                # write the dict to JSON file
                success, error_msg = write_dict_to_jsonfile(default_dict, dict_filepath)
            else:
                error_msg = f"Writing to file '{dict_filepath}' was skipped."

            return_dict = default_dict # use the code-defaults dict passed in

            if success:
                print(f"'{dict_description}' is initialized and written to file '{dict_filepath}'")
            else:
                print(error_msg)
        
        # Convert 'dict_description' dictionary to formatted JSON
        print(f"\nUsing {'external' if dict_filepath_found else 'default'} '{dict_description}':\n{pretty_dict(return_dict)}")

    except Exception as e:
        print(f"ERROR in load_global_dict_from_file() - initializing dict file '{dict_filepath}'\nException: {str(e)}")

        return False, {}
    
    return success, return_dict


DEBUG_SETTINGS_FILE = "/workspace/.debug_settings.json"
DEBUG_SETTINGS = {
    ### these setting will be READ:
    'APP_CONFIGS_MANIFEST_URL': None, # this setting, when not blank, overwrites the global APP_CONFIGS_MANIFEST_URL
    # it also defines the location where the code-defaults will be written to the first time
    'common_settings': {
        'base_download_url': None, # String: this setting, when not blank, overwrites the 'base_download_url' from the 'common_settings of the APP_CONFIGS_MANIFEST
        'verify_app_size': None, # True/False: check the actual app_size against the app_configs "minimum_app_size_kb",
        # when set, it overwrites the 'verify_app_size' from the 'common_settings' of the APP_CONFIGS_MANIFEST
        'delete_unverified_app_path': None, # True/False: delete the APP_PATH from the /workspace folder,
        # if the defined 'minimum_app_size_kb' of the app does not match at minimum the result of 'du -sk' command against the installed app_path
        # when set, it overwrites the 'delete_unverified_app_path' from the 'common_settings' of the APP_CONFIGS_MANIFEST
        'verify_venv_size': None, # True/False: check the actual venv_size against the app_configs "venv_uncompressed_size_kb",
        # when set, it overwrites the 'verify_venv_size' from the 'common_settings' of the APP_CONFIGS_MANIFEST
        'delete_unverified_venv_path': None, # True/False: delete the VENV from the /workspace folder,
        # if the defined 'venv_uncompressed_size_kb' of the app's found 'venv_info' does not match at minimum the result of 'du -sk' command against the installed venv_path
        # when set, it overwrites the 'delete_unverified_venv_path' from the 'common_settings' of the APP_CONFIGS_MANIFEST
        'verify_tolerance_percent': None # percentage (int) factor the 'verify_sizes' for app_path and venv_path are allowed to vary
        # when set, it overwrites the 'verify_tolerance_percent' from the 'common_settings' of the APP_CONFIGS_MANIFEST
    },
    'select_venv_version': None, # when set it overwrites the selected version 'official' or 'latest'
     # can be even any other version like 'experimental', if you provide a 'bXXXX-experimental.tar.gz' VENV archive
     # file, with the correct venv_info checksums/hashes
    'delete_tar_file_after_download': True, # can be set to False to test only local unpack time and github setup and avoid download time
    'skip_to_application_setup': False, # when True, skip download and decompression stage and go directly to GitHub cloning repo installation
    ### KOHYA specific debug settings
    'create_bkohya_to_local_venv_symlink': True, # when True, creates a folder symlink "venv" in "/workspace/kohya_ss" -> "/workspace/bkohya" VENV
    'bkohya_run_tensorboard': True, # autostart tensorboard together with bkohya via cmd_key="run-tensorboard", available at http://localhost:6006/tensorboard/
    # the --noverify flag currently is NOT supported anymore, need to check, in the meantime disable it
    #'bkohya_noverify': False, # when True, the '--noverify' will be inserted into the cmdline and disable requirements verification
    # the default is to check the requirements verification every time when the app starts
    # the idea is to make this a "run-once" option later when we have app-settings
    #
    ### these settings will be WRITTEN for informational purposes:
    'last_app_name': "", # last app_name the code did run for
    'used_venv_version': "", # last venv_version the code used
    'used_local_tarfile': True, # works together with the above TAR local caching setting
    'used_tar_filename': "", # last used local/downloaded tar_filename
    'used_download_url': "", # last used tar download_url
    'total_duration_download': "00:00:00", # timespan-str "hh:mm:ss"
    'total_duration_unpack': "00:00:00", # timespan-str "hh:mm:ss"
    'total_duration': "00:00:00" # timespan-str "hh:mm:ss"
}

def init_debug_settings():
    global DEBUG_SETTINGS

    local_debug = os.environ.get('LOCAL_DEBUG', 'False') # support local browsing for development/debugging
    generate_debug_settings_file = os.environ.get('DEBUG_SETTINGS_FILE', 'False') # generate the DEBUG_SETTINGS_FILE, if not exist already
    write_file_if_not_exists = (local_debug == 'True' or local_debug == 'true' or 
                generate_debug_settings_file == 'True' or generate_debug_settings_file == 'true')

    success, dict = load_global_dict_from_file(DEBUG_SETTINGS, DEBUG_SETTINGS_FILE, "DEBUG_SETTINGS", write_file=write_file_if_not_exists)
    if success:
        DEBUG_SETTINGS = dict

    # read from DEBUG_SETTINGS
    #   installer_codeversion = DEBUG_SETTINGS['installer_codeversion'] # read from DEBUG_SETTINGS

    # write to DEBUG_SETTINGS
    #   write_debug_setting('app_name', "test") # write to DEBUG_SETTINGS
    return

def write_debug_setting(setting_name:str, setting_value:str):
    global DEBUG_SETTINGS
    #DEBUG_SETTINGS = read_dict_from_jsonfile(DEBUG_SETTINGS_FILE)
    DEBUG_SETTINGS[setting_name] = setting_value
    write_dict_to_jsonfile(DEBUG_SETTINGS, DEBUG_SETTINGS_FILE, overwrite=True)


# lutzapps - init some settings from DEBUG_SETTINGS_FILE
init_debug_settings()

APP_CONFIGS_FILE = APP_CONFIGS_MANIFEST_URL # default is the online manifest url defined as "master"
# can be overwritten with DEBUG_SETTINGS['APP_CONFIGS_MANIFEST_URL'], e.g. point to "/workspace/app_configs.json"
# which is the file, that is generated when the ENV var LOCAL_DEBUG='True' or the ENV var APP_CONFIGS_FILE='True'
# NOTE: an existing serialized dict in the "/workspace" folder will never be overwritten again from the code defaults,
# and "wins" against the code-defaults. So even changes in the source-code for this dicts will NOT be used,
# when a local file exists. The idea here is that it is possible to overwrite code-defaults.
# BUT as long as the APP_CONFIGS_MANIFEST_URL not gets overwritten, the global "app_configs" dict will be always loaded
# from the central S3 server, or whatever is defined.
# the only way to overwrite this url, is via the hidden DEBUG_SETTINGS_FILE "/workspace/.debug_settings.json"
# the default source-code setting for DEBUG_SETTINGS['APP_CONFIGS_MANIFEST_URL']: "" (is an empty string),
# which still makes the default APP_CONFIGS_MANIFEST_URL the central master.
# only when this setting is not empty, it can win against the central url, but also only when the Url is valid (locally or remote)
# should there be an invalid Url (central or local), or any other problem, then the code-defaults will be used.
#
# The DEBUG_SETTINGS_FILE is a dict which helps during debugging and testing of APP Installations, and generating ENV TAR files.
# It will also NOT be generated as external FILE, as long the same 2 ENV vars, which control the APP_CONFIGS_FILE generation are set:
#   LOCAL_DEBUG='True' or APP_CONFIGS_FILE='True'
#
# SUMMARY: The DEBUG_SETTINGS and APP_CONFIGS (aka app_configs in code) will never be written to the /workspace,
# when the IMAGE is used normally.

def init_app_configs():
    global APP_CONFIGS_MANIFEST_URL
    global APP_CONFIGS_FILE
    global app_configs
    # store 'common_settings' in global module var
    global COMMON_SETTINGS

    # read APP_CONFIGS_MANIFEST_URL from ENV var 
    env_app_configs_manifest_url = os.environ.get('APP_CONFIGS_MANIFEST_URL', '')
    if not (env_app_configs_manifest_url == None or env_app_configs_manifest_url == ''):
        print(f"using APP_CONFIGS_MANIFEST_URL from ENV_SETTINGS: {env_app_configs_manifest_url}")
        APP_CONFIGS_MANIFEST_URL = env_app_configs_manifest_url
        APP_CONFIGS_FILE = APP_CONFIGS_MANIFEST_URL

    # check for overwrite of APP_CONFIGS_MANIFEST_URL
    debug_app_configs_manifest_url = DEBUG_SETTINGS['APP_CONFIGS_MANIFEST_URL']
    if not (debug_app_configs_manifest_url == None or debug_app_configs_manifest_url == ''):
        print(f"using APP_CONFIGS_MANIFEST_URL from DEBUG_SETTINGS: {debug_app_configs_manifest_url}")
        APP_CONFIGS_MANIFEST_URL = debug_app_configs_manifest_url
        APP_CONFIGS_FILE = APP_CONFIGS_MANIFEST_URL

    print(f"\nUsing APP_CONFIGS_MANIFEST_URL={APP_CONFIGS_MANIFEST_URL}")

    local_debug = os.environ.get('LOCAL_DEBUG', 'False') # support local browsing for development/debugging
    generate_app_configs_file = os.environ.get('APP_CONFIGS_FILE', 'False') # generate the APP_CONFIGS_FILE, if not exist already

    generate_default_app_configs_file = \
        (generate_app_configs_file == 'True' or generate_app_configs_file == 'true' or \
        local_debug == 'True' or local_debug == 'true')

    write_file_if_not_exists = (("://" not in APP_CONFIGS_FILE) and generate_default_app_configs_file)
    
    success, dict = load_global_dict_from_file(app_configs, APP_CONFIGS_FILE, "APP_CONFIGS", write_file=write_file_if_not_exists)
 
    if success: # if the passed-in APP_CONFIGS_MANIFEST_URL was valid and loaded successfully
        app_configs = dict # it overwrite the code-defaults (from local or external/online MANIFEST JSON settings file)
    else: # 404 not found MANIFEST_URL, fall-back to app_configs = <code-defaults already initialized>
        APP_CONFIGS_MANIFEST_URL += f"#not_found_using_code_defaults" # mark the code-default fall-back
        if generate_default_app_configs_file: # LOCAL_DEBUG='True' or APP_CONFIGS_FILE='True'
            default_app_configs_filepath = "/workspace/app_configs(default).json"
            # write the default dict from code to JSON default file and overwrite existing (old) files
            success = write_dict_to_jsonfile(app_configs, default_app_configs_filepath, overwrite=True)

    # if initialized a second/third/... time from code-defaults (404 not found of MANIFEST_URL),
    # 'common_settings' is already removed from the app_configs dict in RAM, so check for this edge case
    if 'common_settings' in app_configs: # first init from code or first/second load from existing MANIFEST URL
        # transfer this 'common_settings' sub dictionary into the global module dict COMMON_SETTINGS
        COMMON_SETTINGS = app_configs['common_settings']
        # before we return the app_configs dict,
        app_configs = remove_app_config('common_settings') # remove 'common_settings', as it is not an "app"

    # process DEBUG_SETTINGS['common_settings'] overwrites
    if not 'common_settings' in DEBUG_SETTINGS:
        return # no 'common_settings' overwrite section found
    
    # loop thru all 'common_settings' from the DEBUG_SETTINGS_FILE and look for overwrites
    for key, value in DEBUG_SETTINGS['common_settings'].items():
        if not value == None or value == '': # if the setting is defned (not None and not a blank string)
            COMMON_SETTINGS[key] = value # overwrite the corresponding app_configs COMMON_SETTING from DEBUG_SETTINGS['common_settings']

    # if app_configs['common_settings']['base_download_url'] is not explicitly set, 
    # the default is to dynamically generate the 'base download url' from the APP_CONFIGS_MANIFEST_URL domain
    # ('production' or 'development' S3 bucket MANIFEST URL), so switching the MANIFEST URL
    # also switches the VENV base download locations, as VENV urls are defined as "RELATIVE" urls in the app_configs by default
    # this 'base_download_url' again could be overwritten via DEBUG_SETTINGS['common_settings']['base_download_url']
    if COMMON_SETTINGS['base_download_url'] == None or COMMON_SETTINGS['base_download_url'] == '':
        # if there is no 'base_download_url' already defined until here, generate it based from the MANIFEST_URL domain
        COMMON_SETTINGS['base_download_url'] = f"{os.path.dirname(APP_CONFIGS_MANIFEST_URL)}/" # append a final '/' for clarifying it is a base folder url
    
    return

init_app_configs() # load from JSON file (local or remote) with code-defaults otherwise


# lutzapps - add kohya_ss support and handle the required local "venv" within the "kohya_ss" app folder
def ensure_kohya_local_venv_is_symlinked() -> tuple[bool, str]:
    ### create a folder symlink for kohya's "local" 'venv' dir
    # as kohya_ss' "setup.sh" assumes a "local" VENV under "/workspace/kohya_ss/venv",
    # we will create a folder symlink "/workspace/kohya_ss/venv" -> "/workspace/bkohya"
    # to our global VENV and rename the original "venv" folder to "venv(BAK)", if any exists,
    # which will be not the case normally.

    if not DEBUG_SETTINGS['create_bkohya_to_local_venv_symlink']:
        return True, "" # not fix the local KOHYA_SS VENV requirement

    import shutil

    try:
        app_configs = get_app_configs()
        bapp_name = "bkohya"
        bapp_venv_path = app_configs[bapp_name]["venv_path"] # '/workspace/bkohya'
        bapp_app_path = app_configs[bapp_name]["app_path"] # '/workspace/kohya_ss'
        bapp_app_path_venv = f"{bapp_app_path}/venv" # '/workspace/kohya_ss/venv'

        name = app_configs[bapp_name]["name"]

        if not os.path.exists(bapp_app_path): # kohya is not installed
            return True, f"{name} is not installed." # no need to fix the local KOHYA VENV

        # check the src-folder of 'bkohya' downloaded VENV exists
        if not os.path.exists(bapp_venv_path): # src_path to bkohya downloaded venv does NOT exists
            return True, f"{name} VENV is not installed." # no need to fix the local KOHYA VENV, as the global KOHYA VENV does not exist

        # kohya_ss is installed
        if os.path.isdir(bapp_app_path_venv): # and has a local "venv" folder

            # check if this local VENV is a folderlink to target the bkohya global VENV to venv_path
            if os.path.islink(bapp_app_path_venv):
                success_message = f"kohya_ss local venv folder '{bapp_app_path_venv}' is already symlinked"

                print(success_message)
                return True, success_message

            # not a folder symlink, but a physical folder,
            ### rename the existing venv folder to BAK (collision-free)
            bak_venv_path = f"{bapp_app_path_venv}(BAK)"
            i = 0
            suffix = ""
            while os.path.exists(f"{bak_venv_path}{suffix}"):
                i += 1
                suffix = str(i)

            bak_venv_path += suffix # free target name for "rename"(move) operation of the folder
            shutil.move(bapp_app_path_venv, bak_venv_path) # move=rename
            
            print(f"local venv folder '{bapp_app_path_venv}' detected and renamed to '{bak_venv_path}'")

        # now the path to the local "venv" is free, if it was already created it is now renamed
        ### create a folder symlink for kohya's "local" venv dir
        # create a folder symlink for kohya local venv dir
        os.symlink(bapp_venv_path, bapp_app_path_venv, target_is_directory=True)
        success_message = f"created a symlink for kohya_ss local venv folder: '{bapp_app_path_venv}' -> '{bapp_venv_path}'"
        print(success_message)

        return True, success_message
            
    except Exception as e:
        error_message = f"ensure_kohya_local_venv_is_symlinked() failed: {str(e)}"
        print(error_message)

        return False, error_message
    
# lutzapps - add kohya_ss venv support
ensure_kohya_local_venv_is_symlinked()

# some verification steps of the VENV setup of the "kohya_ss" app:
# even if it "looks" like the "venv" is in a local sub-folder of the "kohya_ss" dir,
# this location is only "aliased/symlinked" there from the globally downloaded
# tarfile "bkohya.tar.gz" which was expanded spearately into the folder "/workspace/bkohya".
# So the VENV can be redownloaded separately from the github app at "/workspace/kohya_ss"
    # root@9452ad7f4cd6:/workspace/kohya_ss# python --version
    # Python 3.11.10
    # root@fe889cc68f5a:/workspace/kohya_ss# pip --version
    # pip 24.3.1 from /usr/local/lib/python3.11/dist-packages/pip (python 3.11)
    #
    # root@9452ad7f4cd6:/workspace/kohya_ss# python3 --version
    # Python 3.11.10
    # root@fe889cc68f5a:/workspace/kohya_ss# pip3 --version
    # pip 24.3.1 from /usr/local/lib/python3.11/dist-packages/pip (python 3.11)
    #
    # root@9452ad7f4cd6:/workspace/kohya_ss# ls venv -la
    # lrwxr-xr-x 1 root root 17 Nov  8 00:06 venv -> /workspace/bkohya
    #
    # root@9452ad7f4cd6:/workspace/kohya_ss# source venv/bin/activate
    #
    # (bkohya) root@9452ad7f4cd6:/workspace/kohya_ss# ls venv/bin/python* -la
    # lrwxr-xr-x 1 root root 10 Nov  8 00:48 venv/bin/python -> python3.10
    # lrwxr-xr-x 1 root root 10 Nov  8 00:48 venv/bin/python3 -> python3.10
    # lrwxr-xr-x 1 root root 19 Nov  8 00:48 venv/bin/python3.10 -> /usr/bin/python3.10
    #
    # (bkohya) root@9452ad7f4cd6:/workspace/kohya_ss# python --version
    # Python 3.10.12
    # (bkohya) root@fe889cc68f5a:/workspace/kohya_ss# pip --version
    # pip 22.0.2 from /workspace/venv/lib/python3.10/site-packages/pip (python 3.10)
    #
    # (bkohya) root@9452ad7f4cd6:/workspace/kohya_ss# python3 --version
    # Python 3.10.12
    # (bkohya) root@fe889cc68f5a:/workspace/kohya_ss# pip3 --version
    # pip 22.0.2 from /workspace/venv/lib/python3.10/site-packages/pip (python 3.10)
    #
    # (bkohya) root@9452ad7f4cd6:/workspace/kohya_ss# deactivate
    # root@9452ad7f4cd6:/workspace/kohya_ss#
