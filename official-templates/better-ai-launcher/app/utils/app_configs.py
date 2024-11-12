import os
import xml.etree.ElementTree as ET
import requests
import urllib.request
import json

# this is the replacement for the XML manifest, and defines all app_configs in full detail
APP_CONFIGS_MANIFEST_URL = "https://better.s3.madiator.com/app_configs.json"
# if this JSON can not be downloaded, the below code defaults apply
# this app_configs dict can also be generated from code when at least one of following
# 2 ENV vars are found with following values:
# 1.    LOCAL_DEBUG = 'True' # this ENV var should not be passed when in the RUNPOD environment, as it disabled the CF proxy Urls of the App-Manager
#       and this ENV var also controls some other aspects of the app.
#
# 2.    APP_CONFIGS_FILE = 'True' # only exists for this one purpose, to generate the below Dict as file
#       "/workspace/_app_configs.json", which then can be uploaded to the above defined APP_CONFIGS_MANIFEST_URL
# NOTE: 

app_configs = {
    'bcomfy': {
        'id': 'bcomfy',
        'name': 'Better Comfy UI',
        'command': 'cd /workspace/bcomfy && . ./bin/activate && cd /workspace/ComfyUI && python main.py --listen --port 3000 --enable-cors-header',
        'venv_path': '/workspace/bcomfy',
        'app_path': '/workspace/ComfyUI',
        'port': 3000,
        'download_url': 'https://better.s3.madiator.com/bcomfy/bcomfy.tar.gz', # (2024-11-08 18:50:00Z - lutzapps)
        #'venv_uncompressed_size': 6452737952, # uncompressed size of the tar-file (in bytes) - lutzapps new version
        'venv_uncompressed_size': 6155295493, # uncompressed size of the tar-file (in bytes) - original version
        #'archive_size': 3389131462 # tar filesize (in bytes) - lutzapps new version
        'archive_size': 3179595118, # tar filesize (in bytes) - original version
        #'sha256_hash': '18e7d71b75656924f98d5b7fa583aa7c81425f666a703ef85f7dd0acf8f60886', # lutzapps new version
        'sha256_hash': '7fd60808a120a1dd05287c2a9b3d38b3bdece84f085abc156e0a2ee8e6254b84', # original version
        'repo_url': 'https://github.com/comfyanonymous/ComfyUI.git',
        'branch_name': '', # empty branch_name means default = 'master'
        'commit': '', # or commit hash (NYI)
        'recursive': False,
        'refresh': False,
        'custom_nodes': [ # following custom_nodes will be git cloned and installed with "pip install -r requirements.txt" (in Testing)
            {
                'name': 'ComfyUI-Manager (ltdrdata)', # this node is installed in the VENV
                'path': 'ComfyUI-Manager',
                'repo_url': 'https://github.com/ltdrdata/ComfyUI-Manager.git'
            },
            {
                'name': 'ComfyUI-Essentials (cubic)', # this node is installed in the VENV
                'path': 'ComfyUI_essentials',
                'repo_url': 'https://github.com/cubiq/ComfyUI_essentials'
            }
            ### planned custom nodes - To Be Discussed
            # {
            #     'name': 'rgthree comfy',
            #     'path': 'rgthree-comfy',
            #     'repo_url': 'https://github.com/rgthree/rgthree-comfy'
            # },
            # {
            #     'name': 'was node suite comfyui',
            #     'path': 'was-node-suite-comfyui',
            #     'repo_url': 'https://github.com/WASasquatch/was-node-suite-comfyui'
            # },
            # {
            #     'name': 'comfyui controlnet aux',
            #     'path': 'comfyui_controlnet_aux',
            #     'repo_url': 'https://github.com/Fannovel16/comfyui_controlnet_aux'
            # },
            # {
            #     'name': 'x-flux-comfyui (XLabs-AI)',
            #     'path': 'x-flux-comfyui',
            #     'repo_url': 'https://github.com/XLabs-AI/x-flux-comfyui'
            # },
            # {
            #     'name': 'ComfyUI-GGUF (city96)',
            #     'path': 'ComfyUI-GGUF',
            #     'repo_url': 'https://github.com/city96/ComfyUI-GGUF'
            # },
            # {
            #     'name': 'ComfyUI-Florence2 (kijai)',
            #     'path': 'ComfyUI-Florence2F',
            #     'repo_url': 'https://github.com/kijai/ComfyUI-Florence2'
            # },
            # {
            #     'name': 'ComfyUI-KJNodes (kijai)',
            #     'path': 'ComfyUI-KJNodes',
            #     'repo_url': 'https://github.com/kijai/ComfyUI-KJNodes'
            # },
            # {
            #     'name': 'ComfyUI_UltimateSDUpscale (ssitu)',
            #     'path': 'ComfyUI_UltimateSDUpscale',
            #     'repo_url': 'https://github.com/ssitu/ComfyUI_UltimateSDUpscale'
            # },
            # {
            #     'name': 'ControlAltAI Nodes (gseth)',
            #     'path': 'ControlAltAI-Nodes',
            #     'repo_url': 'https://github.com/gseth/ControlAltAI-Nodes'
            # },
            # {
            #     'name': 'ComfyUI Easy-Use (yolain)',
            #     'path': 'ComfyUI-Easy-Use',
            #     'repo_url': 'https://github.com/yolain/ComfyUI-Easy-Use'
            # },
            # {
            #     'name': 'ComfyUI Impact-Pack (tdrdata)',
            #     'path': 'ComfyUI-Impact-Pack',
            #     'repo_url': 'https://github.com/ltdrdata/ComfyUI-Impact-Pack'
            # }
        ]
    },
    'bforge': {
        'id': 'bforge', # app_name
        'name': 'Better Forge',
        'command': 'cd /workspace/bforge && . ./bin/activate && cd /workspace/stable-diffusion-webui-forge && ./webui.sh -f --listen --enable-insecure-extension-access --api --port 7862',
        'venv_path': '/workspace/bforge',
        'app_path': '/workspace/stable-diffusion-webui-forge',
        'port': 7862,
        'download_url': 'https://better.s3.madiator.com/bforge/bforge.tar.gz',
        'venv_uncompressed_size': 7689838771, # uncompressed size of the tar-file (in bytes),
        'archive_size': 3691004078, # tar filesize (in bytes)
        'sha256_hash': 'e87dae2324a065944c8d36d6ac4310af6d2ba6394f858ff04a34c51aa5f70bfb',
        'repo_url': 'https://github.com/lllyasviel/stable-diffusion-webui-forge.git',
        'branch_name': '', # empty branch_name means default = 'master'
        'commit': '', # or commit hash (NYI)
        'clone_recursive': False,
        'refresh': False
    },
    'ba1111': {
        'id': 'ba1111', # app_name
        'name': 'Better A1111',
        'command': 'cd /workspace/ba1111 && . ./bin/activate && cd /workspace/stable-diffusion-webui && ./webui.sh -f --listen --enable-insecure-extension-access --api --port 7863',
        'venv_path': '/workspace/ba1111',
        'app_path': '/workspace/stable-diffusion-webui',
        'port': 7863,
        'download_url': 'https://better.s3.madiator.com/ba1111/ba1111.tar.gz',
        'venv_uncompressed_size': 6794367826, # uncompressed size of the tar-file (in bytes),
        'archive_size': 3383946179, # tar filesize (in bytes)
        'sha256_hash': '1d70276bc93f5f992a2e722e76a469bf6a581488fa1723d6d40739f3d418ada9',
        'repo_url': 'https://github.com/AUTOMATIC1111/stable-diffusion-webui.git',
        'branch_name': '', # empty branch_name means default = 'master'
        'commit': '', # or commit hash (NYI)
        'clone_recursive': False,
        'refresh': False
    },
    'bkohya': {
        'id': 'bkohya', # app_name
        'name': 'Better Kohya',
        'command': 'cd /workspace/bkohya && . ./bin/activate && cd /workspace/kohya_ss && python ./kohya_gui.py --headless --share --server_port 7864', # TODO!! check other ""./kohya_gui.py" cmdlines options
        # need to check: 
        # python ./kohya_gui.py --inbrowser --server_port 7864
        # works for now:
        # python ./kohya_gui.py --headless --share --server_port 7864
        # creates a gradio link for 72h like e.g. https://b6365c256c395e755b.gradio.live
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
        #             [--noverify]
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

        'venv_path': '/workspace/bkohya',
        'app_path': '/workspace/kohya_ss',
        'port': 7864,
        'download_url': 'https://better.s3.madiator.com/bkohya/kohya.tar.gz', # (2024-11-08 13:13:00Z) - lutzapps
        'venv_uncompressed_size': 12128345264, # uncompressed size of the tar-file (in bytes)
        'archive_size': 6314758227, # tar filesize (in bytes)
        'sha256_hash': '9a0c0ed5925109e82973d55e28f4914fff6728cfb7f7f028a62e2ec1a9e4f60a',
        'repo_url': 'https://github.com/bmaltais/kohya_ss.git',
        'branch_name': 'sd3-flux.1', # make sure we use Kohya with FLUX support branch
        # this branch also uses a 'sd-scripts' HEAD branch of 'SD3', which gets automatically checked-out too
        'commit': '', # or commit hash (NYI)
        'clone_recursive': True, # is recursive clone
        'refresh': False        
    }
}

# lutzapps - not used anymore TODO: remove later
""" def fetch_app_info():
    manifest_url = "https://better.s3.madiator.com/"
    download_base_url = "https://better.s3.madiator.com/" # could be different base as the manifest file

    app_info = {}

    try: # be graceful when the server is not reachable, be it S3 or anything else
        response = requests.get(manifest_url)
        root = ET.fromstring(response.content)

        for content in root.findall('{http://s3.amazonaws.com/doc/2006-03-01/}Contents'):
            app_name_and_url = content.find('{http://s3.amazonaws.com/doc/2006-03-01/}Key').text

            app_name = app_name_and_url.split('/')[0] # e.g. "bkohya/bkohya.tar.gz" -> "bkohya"
            download_url = os.path.join(download_base_url, app_name_and_url)

            if not (app_name in ['ba1111', 'bcomfy', 'bforge', 'bkohya']):
                continue # skip unsupported app

            # load code defaults
            archive_size = app_configs[app_name]["archive_size"]
            venv_uncompressed_size = app_configs[app_name]["venv_uncompressed_size"]
            sha256_hash = app_configs[app_name]["sha256_hash"]

            try: # try to find overwrites from code defaults
                archive_size = int(content.find('archive_size').text)
                venv_uncompressed_size = int(content.find('{http://s3.amazonaws.com/doc/2006-03-01/}venv_uncompressed_size').text)
                sha256_hash = int(content.find('{http://s3.amazonaws.com/doc/2006-03-01/}sha256_hash').text)
            except: # swallow any exception, mainly from not being defined (yet) in the XML manifest
                print(f"App '{app_name}' Metadata could not be found in manifest '{manifest_url}', using code defaults!")

            app_info[app_name] = {
                'download_url': download_url,
                'archive_size': archive_size,
                'venv_uncompressed_size': venv_uncompressed_size, # TODO: provide in XML manifest
                'sha256_hash': sha256_hash # TODO: provide in XML manifest
            }

    except requests.RequestException as e: # server not reachable, return empty dict
        print(f"Manifest Url '{manifest_url}' not reachable, using code defaults!")

    return app_info
 """
# lutzapps - not used anymore TODO: remove later
""" def update_app_configs():
    app_info = fetch_app_info()
    for app_name, info in app_info.items():
        if app_name in app_configs:
            app_configs[app_name].update(info) """

def get_app_configs() -> dict:
    return app_configs

def add_app_config(app_name, config):
    app_configs[app_name] = config

def remove_app_config(app_name):
    if app_name in app_configs:
        del app_configs[app_name]

# Update app_configs when this module is imported
# lutzapps - not used anymore TODO: remove later
#update_app_configs()


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
        if ":" in json_filepath: # filepath is online Url containing ":" like http:/https:/ftp:
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

# helper function for "init_app_install_dirs(), "init_shared_model_app_map()", "init_shared_models_folders()" and "inir_DEBUG_SETTINGS()"
def load_global_dict_from_file(default_dict:dict, dict_filepath:str, dict_description:str, SHARED_MODELS_DIR:str="", write_file:bool=True) -> tuple[bool, dict]:
    # returns the 'dict' for 'dict_description' from 'dict_filepath'

    success = False
    return_dict = {}

    try:
        if not SHARED_MODELS_DIR == "" and not os.path.exists(SHARED_MODELS_DIR):
            print(f"\nThe SHARED_MODELS_DIR '{SHARED_MODELS_DIR}' is not found!\nCreate it by clicking the 'Create Shared Folders' button from the WebUI 'Settings' Tab\n")
            
            return False, return_dict
        
        # read from file, if filepath is online url (http:/https:/ftp:) or local filepath exists
        if ":" in dict_filepath or \
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
            # write the dict to JSON file
            success, ErrorMsg = write_dict_to_jsonfile(default_dict, dict_filepath)

            if success:
                print(f"'{dict_description}' is initialized and written to file '{dict_filepath}'")
            else:
                print(ErrorMsg)
        
        # Convert 'dict_description' dictionary to formatted JSON
        print(f"\nUsing {'external' if dict_filepath_found else 'default'} '{dict_description}':\n{pretty_dict(return_dict)}")

    except Exception as e:
        print(f"ERROR in load_global_dict_from_file() - initializing dict file '{dict_filepath}'\nException: {str(e)}")

        return False, {}
    
    return success, return_dict


DEBUG_SETTINGS_FILE = "/workspace/_debug_settings.json"
DEBUG_SETTINGS = {
    # these setting will be READ:
    "APP_CONFIGS_MANIFEST_URL": "", # this setting, when not blank, overwrites the global APP_CONFIGS_MANIFEST_URL
    "installer_codeversion": "v2", # can be "v1" (original) or "v2" (fast)
    "delete_tar_file_after_download": True, # can be set to True to test only local unpack time and github setup
    "create_bkohya_to_local_venv_symlink": True, # when True, creates a folder symlink "venv" in "/workspace/kohya_ss" -> "/workspace/bkohya" VENV
    "skip_to_github_stage": False, # when True, skip download and decompression stage and go directly to GH repo installation
    # these settings will be WRITTEN:
    "app_name": "", # last app_name the code run on
    "used_local_tarfile": True, # works together with the above TAR local caching
    "tar_filename": "", # last local tar_filename used
    "download_url": "", # last used tar download_url
    "total_duration_download": "00:00:00", # timespan-str "hh:mm:ss"
    "total_duration_unpack": "00:00:00", # timespan-str "hh:mm:ss"
    "total_duration": "00:00:00" # timespan-str "hh:mm:ss"
}

def init_debug_settings():
    global DEBUG_SETTINGS

    local_debug = os.environ.get('LOCAL_DEBUG', 'False') # support local browsing for development/debugging
    generate_debug_settings_file = os.environ.get('DEBUG_SETTINGS_FILE', 'False') # generate the DEBUG_SETTINGS_FILE, if not exist already
    write_file_if_not_exists = (local_debug == 'True' or local_debug == 'true' or generate_debug_settings_file == 'True' or generate_debug_settings_file == 'true')

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
# can be overwritten with DEBUG_SETTINGS['APP_CONFIGS_MANIFEST_URL'], e.g. point to "/workspace/_app_configs.json"
# # which is the file, that is generated when the ENV var LOCAL_DEBUG='True' or the ENV var APP_CONFIGS_FILE='True'
# NOTE: an existing serialized dict in the "/workspace" folder will never be overwritten agin from the code defaults,
# and "wins" against the code-defaults. So even changes in the source-code for this dicts will NOT be used,
# when a local file exists. The idea here is that it is possible to overwrite code-defaults.
# BUT as long as the APP_CONFIGS_MANIFEST_URL not gets overwritten, the global "app_configs" dict will be always loaded
# from the central S3 server, or whatever is defined.
# the only way to overwrite this url, is via the DEBUG_SETTINGS_FILE "/workspace/_debug_settings.json"
# the default source-code setting for DEBUG_SETTINGS['APP_CONFIGS_MANIFEST_URL']: "" (is an empty string),
# which still makes the default APP_CONFIGS_MANIFEST_URL the central master.
# only when this setting is not empty, it can win against the central url, but also only when the Url is valid (locally or remote)
# should there be an invalid Url (central or local), or any other problem, then the code-defaults will be used.
#
# The DEBUG_SETTINGS_FILE is a dict which helps during debugging, testing of APP Installations,
# and generating ENV TAR files.
# Is will also NOT be generated as external FILE, as long the same 2 ENV vars, which control the APP_CONFIGS_FILE generation are set:
# LOCAL_DEBUG='True' or APP_CONFIGS_FILE='True'
#
# SUMMARY: The DEBUG_SETTINGS and APP_CONFIGS (aka app_configs in code) will never be written to the /workspace,
# when the IMAGE is used normally.

def init_app_configs():
    global APP_CONFIGS_MANIFEST_URL
    global APP_CONFIGS_FILE
    global app_configs

    # check for overwrite of APP_CONFIGS_MANIFEST_URL
    debug_app_configs_manifest_url = DEBUG_SETTINGS['APP_CONFIGS_MANIFEST_URL']
    if not debug_app_configs_manifest_url == "":
        print(f"using APP_CONFIGS_MANIFEST_URL from DEBUG_SETTINGS: {debug_app_configs_manifest_url}")
        APP_CONFIGS_MANIFEST_URL = debug_app_configs_manifest_url
        APP_CONFIGS_FILE = APP_CONFIGS_MANIFEST_URL


    print(f"\nUsing APP_CONFIGS_MANIFEST_URL={APP_CONFIGS_MANIFEST_URL}")

    local_debug = os.environ.get('LOCAL_DEBUG', 'False') # support local browsing for development/debugging
    generate_app_configs_file = os.environ.get('APP_CONFIGS_FILE', 'False') # generate the APP_CONFIGS_FILE, if not exist already
    write_file_if_not_exists = (local_debug == 'True' or local_debug == 'true' or generate_app_configs_file == 'True' or generate_app_configs_file == 'true')

    success, dict = load_global_dict_from_file(app_configs, APP_CONFIGS_FILE, "APP_CONFIGS", write_file=write_file_if_not_exists)
 
    if success:
        app_configs = dict # overwrite code-defaults (from local or external/online JSON settings file)
    #else app_configs = <code defaults already initialized>

    return

init_app_configs() # load from JSON file (local or remote) with code-defaults otherwise

# lutzapps - add kohya_ss support and handle the required local "venv" within the "kohya_ss" app folder
def ensure_kohya_local_venv_is_symlinked() -> tuple[bool, str]:
    ### create a folder symlink for kohya's "local" 'venv' dir
    # as kohya_ss' "setup.sh" assumes a "local" VENV under "/workspace/kohya_ss/venv",
    # we will create a folder symlink "/workspace/kohya_ss/venv" -> "/workspace/bkohya"
    # to our global VENV and rename the original "venv" folder to "venv(BAK)", if any exists,
    # will we not the case normally.

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
