import os
import xml.etree.ElementTree as ET
import requests
import json

def fetch_app_info():
    url = "https://better.s3.madiator.com/"
    response = requests.get(url)
    root = ET.fromstring(response.content)

    app_info = {}
    for content in root.findall('{http://s3.amazonaws.com/doc/2006-03-01/}Contents'):
        key = content.find('{http://s3.amazonaws.com/doc/2006-03-01/}Key').text
        size = int(content.find('{http://s3.amazonaws.com/doc/2006-03-01/}Size').text)
        app_name = key.split('/')[0]

        # lutzapps - fix "bug" in key element of the S3 XML document
        # all other three apps have a "key" element like "bcomfy/bcomfy.tar.gz" or "bforge/bforge.tar.gz",
        # with their "app_name" prefix + "/" + tar_filename
        # only kohya is missing this "app_name" prefix and has a key element of only its tar_filename "bkohya.tar.gz"
        # this results in the app_name "bkohya.tar.gz", instead of only "bkohya"
        # TODO for madiator - move the "bkohya.tar.gz" into a subfolder "bkohya" in your S3 bucket
        app_name = app_name.replace(".tar.gz", "") # cut any extension postfixes resulting from the wrong key.split() command
        
        if app_name in ['ba1111', 'bcomfy', 'bforge', 'bkohya']: # lutzapps - added new kohya app
            app_info[app_name] = {
                'download_url': f"https://better.s3.madiator.com/{key}",
                'size': size
            }

    return app_info

app_configs = {
    'bcomfy': {
        'name': 'Better Comfy UI',
        'command': 'cd /workspace/bcomfy && . ./bin/activate && cd /workspace/ComfyUI && python main.py --listen --port 3000 --enable-cors-header',
        'venv_path': '/workspace/bcomfy',
        'app_path': '/workspace/ComfyUI',
        'port': 3000,
    },
    'bforge': {
        'name': 'Better Forge',
        'command': 'cd /workspace/bforge && . ./bin/activate && cd /workspace/stable-diffusion-webui-forge && ./webui.sh -f --listen --enable-insecure-extension-access --api --port 7862',
        'venv_path': '/workspace/bforge',
        'app_path': '/workspace/stable-diffusion-webui-forge',
        'port': 7862,
    },
    'ba1111': {
        'name': 'Better A1111',
        'command': 'cd /workspace/ba1111 && . ./bin/activate && cd /workspace/stable-diffusion-webui && ./webui.sh -f --listen --enable-insecure-extension-access --api --port 7863',
        'venv_path': '/workspace/ba1111',
        'app_path': '/workspace/stable-diffusion-webui',
        'port': 7863,
    },
    'bkohya': {
        'name': 'Better Kohya',
        'command': 'cd /workspace/bkohya && . ./bin/activate && cd /workspace/kohya_ss && ./gui.sh --listen --port 7860',
        'venv_path': '/workspace/bkohya',
        'app_path': '/workspace/kohya_ss',
        'port': 7860,
    }
}

def update_app_configs():
    app_info = fetch_app_info()
    for app_name, info in app_info.items():
        if app_name in app_configs:
            app_configs[app_name].update(info)

def get_app_configs():
    return app_configs

def add_app_config(app_name, config):
    app_configs[app_name] = config

def remove_app_config(app_name):
    if app_name in app_configs:
        del app_configs[app_name]

# Update app_configs when this module is imported
update_app_configs()


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
        
        # Write the JSON data to a file
        with open(json_filepath, 'w', encoding='utf-8') as output_file:
            json.dump(dict, output_file, ensure_ascii=False, indent=4, separators=(',', ': '))

    except Exception as e:
        error_msg = f"ERROR in shared_models:write_dict_to_jsonfile() - loading JSON Map File '{json_filepath}'\nException: {str(e)}"
        print(error_msg)

        return False, error_msg # failure
    
    return True, "" # success

# helper function called by init_app_install_dirs(), init_shared_model_app_map(), init_shared_models_folders() and init_debug_settings()
def read_dict_from_jsonfile(json_filepath:str) -> dict:
    # Read JSON file from 'json_filepath' and return it as 'dict'

    try:
        if os.path.exists(json_filepath):
            with open(json_filepath, 'r') as input_file:
                dict = json.load(input_file)
        else:
            error_msg = f"dictionary file '{json_filepath}' does not exist"
            #print(error_msg)

            return {}, error_msg # failure

    except Exception as e:
        error_msg = f"ERROR in shared_models:read_dict_from_jsonfile() - loading JSON Map File '{json_filepath}'\nException: {str(e)}"
        print(error_msg)

        return {}, error_msg # failure

    return dict, "" # success

# helper function to return a pretty formatted DICT string for human consumption (Logs, JSON)
def pretty_dict(dict:dict) -> str:
   dict_string = json.dumps(dict, ensure_ascii=False, indent=4, separators=(',', ': '))

   return dict_string

# helper function for "init_app_install_dirs(), "init_shared_model_app_map()", "init_shared_models_folders()" and "inir_debug_settings()"
def init_global_dict_from_file(dict:dict, dict_filepath:str, dict_description:str, SHARED_MODELS_DIR:str="") -> bool:
    # load or initialize the 'dict' for 'dict_description' from 'dict_filepath'

    try:
        if not SHARED_MODELS_DIR == "" and not os.path.exists(SHARED_MODELS_DIR):
            print(f"\nThe SHARED_MODELS_DIR '{SHARED_MODELS_DIR}' is not found!\nCreate it by clicking the 'Create Shared Folders' button from the WebUI 'Settings' Tab\n")
            
            return
        
        if os.path.isfile(dict_filepath) and os.path.exists(dict_filepath):
            dict_filepath_found = True
            # read the dict_description from JSON file
            print(f"\nExisting '{dict_description}' found and read from file '{dict_filepath}'\nThe file overwrites the code defaults!")

            dict, error_msg = read_dict_from_jsonfile(dict_filepath)
            if not error_msg == "":
                print(error_msg)

        else: # init the dict_description from app code
            dict_filepath_found = False
            print(f"No {dict_description}_FILE found, initializing default '{dict_description}' from code ...")
            # use already defined dict from app code
            # write the dict to JSON file
            success, ErrorMsg = write_dict_to_jsonfile(dict, dict_filepath)

            if success:
                print(f"'{dict_description}' is initialized and written to file '{dict_filepath}'")
            else:
                print(ErrorMsg)
        
        # Convert 'dict_description' dictionary to formatted JSON
        print(f"\nUsing {'external' if dict_filepath_found else 'default'} '{dict_description}':\n{pretty_dict(dict)}")

    except Exception as e:
        error_msg = f"ERROR in shared_models:init_global_dict_from_file() - initializing dict Map File '{dict_filepath}'\nException: {str(e)}"
        print(error_msg)

        return False, error_msg
    
    return True, "" # success

DEBUG_SETTINGS_FILE = "/workspace/_debug_settings.json"
DEBUG_SETTINGS = {
    # these setting will be READ:
    "manifests": { # uncompressed sizes of the tar-files
        "bcomfy": {
            "venv_uncompressed_size": 6155283197,
            "sha256_hash": ""
        },
        "ba1111": {
            "venv_uncompressed_size": 6794355530,
            "sha256_hash": ""
        },
        "bforge": {
            "venv_uncompressed_size": 7689838771,
            "sha256_hash": ""
        },
        "bkohya": {
            "venv_uncompressed_size": 12192767148,
            "sha256_hash": ""
        }
    },
    "installer_codeversion": "2", # can be "1" (original) or "2" (fast)
    "delete_tarfile_after_download": "1", # can be set to "0" to test only local unpack time and github setup
    "use_bkohya_tar_folder_fix": "1", # the fix unpacks to "/workspace" and not to "/workspace/bkohya"
    "use_bkohya_local_venv_symlink": "1", # when active, creates a folder symlink "venv" in "/workspace/kohya_ss" -> "/workspace/bkohya" VENV
    # these settings will be WRITTEN:
    "used_local_tar": "0", # works together with the above TAR local caching
    "app_name": "",
    "tar_filename": "",
    "download_url": "",
    "total_duration_download": "0",
    "total_duration_unpack": "0",
    "total_duration": "0"
}

def init_debug_settings():
    global DEBUG_SETTINGS
    init_global_dict_from_file(DEBUG_SETTINGS, DEBUG_SETTINGS_FILE, "DEBUG_SETTINGS")

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

# lutzapps - add kohya_ss support and required local VENV
def ensure_kohya_local_venv_is_symlinked() -> tuple[bool, str]:
    # as kohya_ss' "setup.sh" assumes a "local" VENV under "/workspace/kohya_ss/venv",
    # we will create a folder symlink "/workspace/kohya_ss/venv" -> "/workspace/bkohya"
    # to our global VENV and rename the original "venv" folder to "venv(BAK)"

    if not DEBUG_SETTINGS['use_bkohya_local_venv_symlink'] == "1":
        return True, "" # not fix the local KOHYA_SS VENV

    import shutil

    try:
        app_configs = get_app_configs()
        bapp_name = "bkohya"
        bapp_venv_path = app_configs[bapp_name]["venv_path"] # '/workspace/bkohya'
        bapp_app_path = app_configs[bapp_name]["app_path"] # '/workspace/kohya_ss'
        bapp_app_path_venv = f"{bapp_app_path}/venv" # '/workspace/kohya_ss/venv'

        if not os.path.exists(bapp_app_path): # kohya is not installed
            return True, "" # no need to fix the local KOHYA VENV
        
        # kohya installed and has a local "venv" folder
        if os.path.exists(bapp_app_path_venv) and os.path.isdir(bapp_app_path_venv):

            # check if this local VENV is a folderlink to target our bkohya global VENV to venv_path
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

            bak_venv_path += suffix # free target bame for "rename"
            shutil.move(bapp_app_path_venv, bak_venv_path) # move=rename
            
            print(f"local venv folder '{bapp_app_path_venv}' detected and renamed to '{bak_venv_path}'")

        ### create a folder symlink for kohya's "local" venv dir
        # check the src-folder to kohya downloaded venv exists
        if os.path.exists(bapp_venv_path): # src_path to bkohya downloaded venv exists
            # create a folder symlink for kohya local venv dir
            os.symlink(bapp_venv_path, bapp_app_path_venv, target_is_directory=True)
            success_message = f"created a symlink for kohya_ss local venv folder: '{bapp_venv_path}' -> '{bapp_app_path_venv}'"
            print(success_message)

        return True, success_message
            
    except Exception as e:
        error_message = f"ensure_kohya_local_venv_is_symlinked() failed: {str(e)}"
        print(error_message)

        return False, error_message
    
# lutzapps - add kohya_ss venv support
ensure_kohya_local_venv_is_symlinked()