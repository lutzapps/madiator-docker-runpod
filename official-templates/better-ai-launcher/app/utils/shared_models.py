import os
import shutil
import datetime
import threading
import time

from flask import jsonify
from utils.websocket_utils import (send_websocket_message, active_websockets)
from utils.app_configs import (get_app_configs, load_global_dict_from_file, pretty_dict)

README_FILE_PREFIX = "_readme-" # prefix for all different dynamically generated README file names

### support local docker container runs with locally BOUND Workspace, needed also during local debugging
SHARED_MODELS_DIR = "/workspace/shared_models" # storage root for all shared_models (as designed for production app)

# check for "DISABLE_PULLBACK_MODELS" ENV var, and convert it from String to Boolean
# DISABLE_PULLBACK_MODELS: if not present (or empty) then "pull-back" local model files is enabled [default]
# else local found model files in app model folders will NOT be pulled back (and re-shared) into 'shared_models'
DISABLE_PULLBACK_MODELS = False
disable_pullback = os.environ.get('DISABLE_PULLBACK_MODELS', 'False').lower() # "True" / "true" / "1", or "False" / "false" / "0" / "" (not set)
if not (disable_pullback == "" or disable_pullback == "false" or disable_pullback == "0"):
    DISABLE_PULLBACK_MODELS = True

# check for "DISABLE_PULLBACK_MODELS" ENV var, and convert it from String to Boolean
# LOCAL_DEBUG: if not present (or empty) then run in "production" [default],
# else run as "development" / "debug" version
LOCAL_DEBUG = False
local_debug_str = os.environ.get('LOCAL_DEBUG', 'False').lower() # "True" / "true" / "1", or "False" / "false" / "0" / "" (not set)
if not (local_debug_str == "" or local_debug_str == "false" or local_debug_str == "0"):
    LOCAL_DEBUG = True

# show current configuration
print("\n\n*** SHARED_MODELS module init ***\n")
print(f"SHARED_MODELS_DIR='{SHARED_MODELS_DIR}'\n")

print(f"LOCAL_DEBUG='{LOCAL_DEBUG}'")
print(f"DISABLE_PULLBACK_MODELS='{DISABLE_PULLBACK_MODELS}'")

# show/hide the 3 dictionary MAPPING FILES, which control the whole module
MAKE_MAPPING_FILES_HIDDEN = False # can also be set according to LOCAL_DEBUG  = True or False

if MAKE_MAPPING_FILES_HIDDEN:
    HIDDEN_FILE_PREFIX = "." # filenames starting with a dot (".") are hidden by the filesystem
else:
    HIDDEN_FILE_PREFIX = "" # filenames are shown to the user

print(f"MAKE_MAPPING_FILES_HIDDEN='{MAKE_MAPPING_FILES_HIDDEN}'\n")


# the below SHARED_MODEL_FOLDERS_FILE will be read and used (if exists),
# otherwise this file will be generated with the content of the below default SHARED_MODEL_FOLDERS dict
SHARED_MODEL_FOLDERS_FILE = f"{SHARED_MODELS_DIR}/{HIDDEN_FILE_PREFIX}_shared_model_folders.json"
SHARED_MODEL_FOLDERS = {
    # "model_type" (=subdir_name of SHARED_MODELS_DIR): "model_type_description"
    "ckpt": "Model Checkpoint (Full model including a CLIP and VAE model)",
    "clip": "CLIP Model (used together with UNET models)",
    "controlnet": "ControlNet model (Canny, Depth, Hed, OpenPose, Union-Pro, etc.)",
    "embeddings": "Embedding (aka Textual Inversion) Model",
    "hypernetworks": "HyperNetwork Model",
    "insightface": "InsightFace Model",
    "ipadapters": "ControlNet IP-Adapter Model",
    "ipadapters/xlabs": "IP-Adapter from XLabs-AI",
    "LLM": "LLM (aka Large-Language Model) is folder mapped (1 folder per model), append '/*' in the map", 
    "loras": "LoRA (aka Low-Ranking Adaption) Model",
    "loras/xlabs": "LoRA Model from XLabs-AI",
    "loras/flux": "LoRA Model trained on Flux.1 Dev or Flux.1 Schnell",
    "reactor": "Reactor Model",
    "reactor/faces": "Reactor Face Model",
    "unet": "UNET Model Checkpoint (need separate CLIP and VAE Models)",
    "upscale_models": "Upscaling Model (based on ESRGAN)",
    "vae": "VAE En-/Decoder Model",
    "vae-approx": "Approximate VAE Model"
}

# helper function called by "inline"-main() and ensure_shared_models_folders()
def init_shared_models_folders(send_SocketMessage:bool=True):
    global SHARED_MODEL_FOLDERS
    success, dict = load_global_dict_from_file(SHARED_MODEL_FOLDERS, SHARED_MODEL_FOLDERS_FILE, "SHARED_MODEL_FOLDERS", SHARED_MODELS_DIR)
    if success:
        SHARED_MODEL_FOLDERS = dict

    if os.path.exists(SHARED_MODEL_FOLDERS_FILE) and send_SocketMessage:
        send_websocket_message('extend_ui_helper', {
            'cmd': 'refreshModelTypes',
            'message': 'New ModelTypes are available'
            } )

    return

### "inline"-main() ###
# init the SHARED_MODEL_FOLDERS
init_shared_models_folders(False) # dont send a WS-Message for "Model Downloader" at module init, to init/refresh its modelType list

# ----------

# helper function called from "app.py" via WebUI "Create Shared Folders" button on "Settings" tab
#   ensures 'model_type' sub-folders for Model Mapping and the "Model Downloader" exists
#   in the SHARED_MODELS_DIR (uses above initialized 'SHARED_MODEL_FOLDERS' dict)
def ensure_shared_models_folders():
    try:
        # init global module 'SHARED_MODEL_FOLDERS' dict: { 'model_type' (=subdir_names): 'app_model_dir'
        # from app code or from external JSON 'SHARED_MODEL_FOLDERS_FILE' file
        init_shared_models_folders(False) # (re-)read the SHARED_MODEL_FOLDERS_FILE again, if changed, but don't refresh modelTypes in "Model Downloader" yet

        print(f"(re-)creating 'shared_models' model type sub-folders for Apps and the 'Model Downloader' in folder '{SHARED_MODELS_DIR}':")

        # create the shared_models directory, if it doesn't exist yet
        os.makedirs(f"{SHARED_MODELS_DIR}/", exist_ok=True) # append slash to make sure folder is created

        # create a "__README.txt" file in the shared_models directory
        readme_path = os.path.join(SHARED_MODELS_DIR, '__README.txt')

        with open(readme_path, 'w') as readme_file:
            readme_file.write("Upload your models to the appropriate folders:\n\n")

            for model_type, model_type_description in SHARED_MODEL_FOLDERS.items():
                shared_model_folderpath = os.path.join(SHARED_MODELS_DIR, model_type)
                
                os.makedirs(os.path.dirname(f"{shared_model_folderpath}/"), exist_ok=True) # append trailing "/" to make sure the last sub-folder is created
                print(f"'{model_type}' Folder created for '{model_type_description}'")
                
                model_type_name = model_type
                if model_type_name.endswith('s'): # model_type uses "plural" form with trailing "s"
                    model_type_name = model_type[:-1] # cut the last trailing 's'

                readme_model_type_filename = os.path.join(shared_model_folderpath, f"{README_FILE_PREFIX}{model_type.replace('/', '-')}.txt") # translate "/" from grouping map rule into valid readme filename, e.g. "loras/flux" into "loras-flux"
                readme_model_type_file = open(readme_model_type_filename, 'w') 
                readme_model_type_file.writelines(f"Put your '{model_type_name}' type models here, {model_type_description}") 
                readme_model_type_file.close()

                readme_file.write(f"- {model_type}: for {model_type_name} models, {model_type_description}\n")
            
            readme_file.write("\nThese models will be automatically linked to all supported apps.\n\n")
            readme_file.write("Models directly downloaded into an app model folder will be\n")
            readme_file.write("automatically pulled back into the corresponding shared folder and relinked back!\n")

        # send a message for the "Model Downloader" to "refresh" its 'modelType' list
        send_websocket_message('extend_ui_helper', {
            'cmd': 'refreshModelTypes',
            'message': 'New ModelTypes are available'
        } )

        return jsonify({'status': 'success', 'message': 'Shared model folders created successfully.'})
    
    except Exception as e:
        print(f"ERROR in shared_models:ensure_shared_model_folder() - Exception:\n{str(e)}")

        return jsonify({'status': 'error', 'message': str(e)})                

# ----------

# the below APP_INSTALL_DIRS_FILE will be read and used (if exists),
# otherwise this file will be generated with the content of the below default APP_INSTALL_DIRS dict
# this dict is very important, as it "defines" part of the symlink path,
# together with below defined SHARED_MODEL_APP_MAP (which uses relative path to the "app_install_dir" aka 'app_path')
APP_INSTALL_DIRS_FILE = f"{SHARED_MODELS_DIR}/{HIDDEN_FILE_PREFIX}_app_install_dirs.json"
APP_INSTALL_DIRS = {
    # "app_name": "app_install_dir"
    "A1111": "/workspace/stable-diffusion-webui",
    "Forge": "/workspace/stable-diffusion-webui-forge",
    "ComfyUI": "/workspace/ComfyUI",
    "kohya_ss": "/workspace/kohya_ss",
    "CUSTOM1": "/workspace/joy-caption-batch"
}

# the code from Madiator also defines a similar 'app_configs' dictionary
# but the idea here is also to allow "CUSTOM" Apps, installed by the user manually,
# to participate in "shared_models" model sharing

# app_configs = {
#     'bcomfy': {
#         'name': 'Better Comfy UI',
#         'command': 'cd /workspace/bcomfy && . ./bin/activate && cd /workspace/ComfyUI && python main.py --listen --port 3000 --enable-cors-header',
#         'venv_path': '/workspace/bcomfy',
#         'app_path': '/workspace/ComfyUI',
#         'port': 3000,
#     },
#     'bforge': {
#         'name': 'Better Forge',
#         'command': 'cd /workspace/bforge && . ./bin/activate && cd /workspace/stable-diffusion-webui-forge && ./webui.sh -f --listen --enable-insecure-extension-access --api --port 7862',
#         'venv_path': '/workspace/bforge',
#         'app_path': '/workspace/stable-diffusion-webui-forge',
#         'port': 7862,
#     },
#     'ba1111': {
#         'name': 'Better A1111',
#         'command': 'cd /workspace/ba1111 && . ./bin/activate && cd /workspace/stable-diffusion-webui && ./webui.sh -f --listen --enable-insecure-extension-access --api --port 7863',
#         'venv_path': '/workspace/ba1111',
#         'app_path': '/workspace/stable-diffusion-webui',
#         'port': 7863,
#     },
#     'bkohya': {
#         'name': 'Better Kohya',
#         'command': 'cd /workspace/bkohya && . ./bin/activate && cd /workspace/kohya_ss && ./gui.sh --listen --port 7860',
#         'venv_path': '/workspace/bkohya',
#         'app_path': '/workspace/kohya_ss',
#         'port': 7860,
#     }
# }

# MAP between Madiator's "app_configs" dict and the "APP_INSTALL_DIRS" dict used in this module
MAP_APPS = {
    "bcomfy": "ComfyUI",
    "bforge": "Forge",
    "ba1111": "A1111",
    "bkohya": "kohya_ss" # lutzapps - added new kohya_ss app
}

# helper function called by main(), uses above "MAP_APPS" dict
def sync_with_app_configs_install_dirs():
    print(f"Syncing 'app_configs' dict 'app_path' into the 'APP_INSTALL_DIRS' dict ...")

    app_configs = get_app_configs()
    for bapp_name, config in app_configs.items():
        if bapp_name in MAP_APPS:
            # get/sync the bapp_path from app_configs dict
            bapp_path = app_configs[bapp_name]["app_path"]
            print(f"\tSyncing 'app_path': '{bapp_path}' from app_configs for app 'name': '{bapp_name}'" )
            APP_INSTALL_DIRS[MAP_APPS[bapp_name]] = bapp_path # update path in APP_INSTALL_DIRS

    # show final synced APP_INSTALL_DIRS
    print(f"\nUsing synched 'APP_INSTALL_DIRS':\n{pretty_dict(APP_INSTALL_DIRS)}")

     
# init global module 'APP_INSTALL_DIRS' dict: { 'app_name': 'app_installdir' }
# default mapping from app code or (if exists) from external JSON 'APP_INSTALL_DIRS_FILE' file 
# NOTE: this APP_INSTALL_DIRS_FILE is temporary synced with the app_configs dict
def init_app_install_dirs():
    global APP_INSTALL_DIRS
    success, dict = load_global_dict_from_file(APP_INSTALL_DIRS, APP_INSTALL_DIRS_FILE, "APP_INSTALL_DIRS", SHARED_MODELS_DIR)
    if success:
        APP_INSTALL_DIRS = dict

    return

### "inline"-main() ###
# init the APP_INSTALL_DIRS and sync it from "app_configs" dict
init_app_install_dirs()
sync_with_app_configs_install_dirs() # TODO: this is temporary and should be merged/integrated better later

# ----------

SHARED_MODEL_APP_MAP_FILE = f"{SHARED_MODELS_DIR}/{HIDDEN_FILE_PREFIX}_shared_model_app_map.json"
# The dictionary 'model_type' "key" is relative to the SHARED_MODELS_DIR "/workspace/shared_models/" main folder.
# The sub dictionary 'app_model_folderpath' value is relative to the 'app_install_dir' value
# of the above APP_INSTALL_DIRS dictionary

# here is a list of all "known" model type dirs, and if they are used here (mapped) or
# if they are currently "unmapped":
#
# "kohya_ss" (mapped): "/models"

# "ComfyUI" (mapped): "/models/checkpoints", "/models/clip", "/models/controlnet", "/models/embeddings", "/models/hypernetworks", "/models/ipadapter/"(???), "/models/loras", "/models/reactor"(???), "/models/unet", "/models/upscale_models", "/models/vae", "/models/vae_approx" 
# "ComfyUI" (unmapped): "/models/clip_vision", "/models/diffusers", "/models/diffusion_models", "/models/gligen", "/models/photomaker", "/moedls/style_models", 

# "A1111"/"Forge" (mapped): "/embeddings", "/models/ControlNet", "/models/ESRGAN", "/models/hypernetworks", "/models/insightface"(???), "/models/Lora", "/models/reactor", "/models/Stable-diffusion", "/models/text_encoder"(???), "/models/VAE", "/models/VAE-approx"
# "A1111"/"Forge" (unmapped): "/model/adetailer", "/models/BLIP", "/models/Codeformer", "models/deepbooru", "/model/Deforum", "/models/GFPGAN", "/models/karlo", "/models/Unet-onnx", "/models/Unet-trt"

SHARED_MODEL_APP_MAP = {
    "ckpt": { # "model_type" (=subdir_name of SHARED_MODELS_DIR)
        # "app_name": "app_model_folderpath" (for this "model_type", path is RELATIVE to "app_install_dir" of APP_INSTALL_DIRS map)
        "ComfyUI": "/models/checkpoints",
        "A1111": "/models/Stable-diffusion",
        "Forge": "/models/Stable-diffusion",
        "kohya_ss": "/models" # flatten all "ckpt" / "unet" models here
    },

    "clip": {
        "ComfyUI": "/models/clip",
        "A1111": "/models/text_encoder",
        "Forge": "/models/text_encoder"
    },

    "controlnet": {
        "ComfyUI": "/models/controlnet",
        "A1111": "/models/ControlNet",
        "Forge": "/models/ControlNet"
        #"A1111": "/extensions/sd-webui-controlnet/models", # SD1.5 ControlNets
        #"Forge": "/extensions/sd-webui-controlnet/models" # SD1.5 ControlNets
    },

    # EMBEDDINGS map outside of models folder for FORGE / A1111
    "embeddings": {
        "ComfyUI": "/models/embeddings",
        "A1111": "/embeddings",
        "Forge": "/embeddings"
    },

    "hypernetworks": {
        "ComfyUI": "/models/hypernetworks",
        "A1111": "/models/hypernetworks",
        "Forge": "/models/hypernetworks"
    },

    "insightface": {
        "ComfyUI": "/models/insightface",
        "A1111": "/models/insightface", # unverified location
        "Forge": "/models/insightface" # unverified location
    },

    "ipadapters": {
        "ComfyUI": "/models/ipadapter/",
        "A1111": "/extensions/sd-webui-controlnet/models", # unverified location
        "Forge": "/extensions/sd-webui-controlnet/models" # unverified location
    },

    "ipadapters/xlabs": { # sub-folders for XLabs-AI IP-Adapters
        "ComfyUI": "/models/xlabs/ipadapters",
        "A1111": "/extensions/sd-webui-controlnet/models", # flatten all "xlabs" ipadapters here
        "Forge": "/extensions/sd-webui-controlnet/models" # flatten all "xlabs" ipadapters here
    },

    # some LoRAs get stored here in sub-folders, e.g. "/xlabs/*"
    "loras": {
        "ComfyUI": "/models/loras",
        "A1111": "/models/Lora",
        "Forge": "/models/Lora"
    },

    # Support "XLabs-AI" LoRA models
    "loras/xlabs": { # special syntax for "grouping"
        "ComfyUI": "/models/loras/xlabs",
        "A1111": "/models/Lora", # flatten all "xlabs" LoRAs here
        "Forge": "/models/Lora" # flatten all "xlabs" LoRAs here
    },

    # Support "Grouping" all FLUX LoRA models into a LoRA "flux" sub-folder for ComfyUI,
    # which again need to be flattened for other apps
    "loras/flux": {
        "ComfyUI": "/models/loras/flux",
        "A1111": "/models/Lora", # flatten all "flux" LoRAs here
        "Forge": "/models/Lora" # flatten all "flux" LoRAs here
    },

    "reactor": {
        "ComfyUI": "/models/reactor", # unverified location
        "A1111": "/models/reactor",
        "Forge": "/models/reactor",
    },

    "reactor/faces": {
        "ComfyUI": "/models/reactor/faces", # unverified location
        "A1111": "/models/reactor",
        "Forge": "/models/reactor",
    },

    # UNET models map into the CKPT folders of all other apps, except for ComfyUI
    "unet": {
        "ComfyUI": "/models/unet",
        "A1111": "/models/Stable-diffusion", # flatten all "ckpts" / "unet" models here
        "Forge": "/models/Stable-diffusion", # flatten all "ckpts" / "unet" models here
        "kohya_ss": "/models" # flatten all "ckpt" / "unet" models here
    },

    "upscale_models": {
        "ComfyUI": "/models/upscale_models",
        "A1111": "/models/ESRGAN",
        "Forge": "/models/ESRGAN"
    },

    "vae": {
        "ComfyUI": "/models/vae",
        "A1111": "/models/VAE",
        "Forge": "/models/VAE"
    },

    "vae-approx": {
        "ComfyUI": "/models/vae_approx",
        "A1111": "/models/VAE-approx",
        "Forge": "/models/VAE-approx"
    },

    # E.g. Custom Apps support for Joytag-Caption-Batch Tool (which uses the "Meta-Llama-3.1-8B" LLM)
    # to share the model with e.g. ComfyUI. This LLM model come as full folders with more than one file!
    # Pay attention to the special syntax for folder mappings (add a "/*" suffix to denote a folder mapping)
    "LLM/Meta-Llama-3.1-8B/*": { # special syntax for "folder" symlink (the "/*" is mandatory)
        "ComfyUI": "/models/LLM/Meta-Llama-3.1-8B/*", # special syntax for "folder" symlink, the "/*" is optional
        "CUSTOM1": "/model/*" # special syntax for "folder" symlink, the "/*" is optional
    }
}

# the "init_shared_model_app_map()" function initializes the
#   global module 'SHARED_MODEL_APP_MAP' dict: 'model_type' -> 'app_name:app_model_dir' (relative path)
# which does a default mapping from app code or (if exists) from external JSON 'SHARED_MODEL_APP_MAP_FILE' file
def init_shared_model_app_map():
    global SHARED_MODEL_APP_MAP
    success, dict = load_global_dict_from_file(SHARED_MODEL_APP_MAP, SHARED_MODEL_APP_MAP_FILE, "SHARED_MODEL_APP_MAP", SHARED_MODELS_DIR)
    if success:
        SHARED_MODEL_APP_MAP = dict

    return

### "inline"-main() ###
# init the SHARED_MODEL_APP_MAP
init_shared_model_app_map()

# ----------


# helper function called by update_model_symlinks()
def remove_broken_model_symlinks(shared_model_folderpath:str, app_model_folderpath:str, model_type:str) -> int:
    # process all files in app_model_folderpath
    print(f"-> process broken '{model_type}' app_model file symlinks, which where removed from their corresponding shared_models sub-folder ...")

    broken_modellinks_count = 0
    broken_modellinks_info = ""

    for app_model_filename in os.listdir(app_model_folderpath):
        app_model_filepath = os.path.join(os.path.join(app_model_folderpath, app_model_filename))

        # check for stale/broken model filelinks and folderlinks (LLMs)
        if os.path.islink(app_model_filepath) and not os.path.exists(app_model_filepath):
            # Remove existing stale/broken symlink
            broken_modellinks_count = broken_modellinks_count + 1
            dateInfo = "{:%b %d, %Y, %H:%M:%S GMT}".format(datetime.datetime.now())
            broken_modellinks_info += f"\t{app_model_filename}\t[@ {dateInfo}]\n"

            os.unlink(app_model_filepath) # try to unlink the file/folder symlink
            # that normally is enough to remove the broken link (and the below code may never run)

            # re-check if file/folder still exists
            if os.path.exists(app_model_filepath): # if file/folder link still exists
                if os.path.isdir(app_model_filepath): # broken folder link
                    shutil.rmtree(app_model_filepath) # remove the linked folder
                else: # broken file link
                    os.remove(app_model_filepath) # remove the file link

            print(f"\tremoved broken symlink for model '{app_model_filepath}'")


    if broken_modellinks_count > 0:
        # maintain (create/append to) a readme file for the app_model_folderpath target folder about the removed/deleted Model File Symlinks
        readme_brokenlinks_models_filepath = os.path.join(app_model_folderpath, f"{README_FILE_PREFIX}brokenlinks-{model_type.replace('/', '-')}.txt") # translate "/" from grouping map rule into valid readme filename, e.g. "loras/flux" into "loras-flux"

        if not os.path.exists(readme_brokenlinks_models_filepath): # no such readme file exists, so create it
            fileHeader = f"Following broken model file links have been found and where deleted from this directory:\n\n"
            file = open(readme_brokenlinks_models_filepath, 'w') # create the file
            file.writelines(fileHeader) # and write the fileHeader once
            file.writelines(broken_modellinks_info) # and add the broken Model File Links
            file.close()
        else: # readme file already existed from before
            file = open(readme_brokenlinks_models_filepath, 'a') # append to file
            file.writelines(broken_modellinks_info) # and add the broken Model File Links
            file.close()

    return broken_modellinks_count


# helper function called by update_model_symlinks()
def pull_unlinked_models_back_as_shared_models(shared_model_folderpath:str, app_model_folderpath:str, model_type:str) -> int:
    # process all files in app_model_folderpath
    print(f"-> process for possibly pulling-back '{model_type}' local app_model files into their corresponding shared_models sub-folder ...")

    pulled_model_files_count = 0
    pulled_model_files_info = ""

    for app_model_filename in os.listdir(app_model_folderpath):
        if app_model_filename.startswith(".") or app_model_filename.startswith(README_FILE_PREFIX):
            continue # skip hidden filenames like ".DS_Store" (on macOS), ".keep" (on GitHub) and all "{README_FILE_PREFIX}*.txt" files
        
        app_model_filepath = os.path.join(app_model_folderpath, app_model_filename)
        if os.path.islink(app_model_filepath) or os.path.isdir(app_model_filepath) or os.path.getsize(app_model_filepath) == 0:
            continue # skip all already symlinked model files and sub-folders and ZERO size "put yout model here" files

        # real file, potentially a model file which can be pulled back "home"
        pulled_model_files_count = pulled_model_files_count + 1
        print(f"processing app model '{app_model_filename}' ...")
        shared_model_filepath = os.path.join(shared_model_folderpath, app_model_filename)
        print(f"moving the file '{app_model_filename}' back to the '{model_type}' shared_models folder")
        shutil.move(app_model_filepath, shared_model_filepath) # move it back to the shared_models model type folder
        
        print(f"\tpulled-back local model '{app_model_filepath}'")

        dateInfo = "{:%b %d, %Y, %H:%M:%S GMT}".format(datetime.datetime.now())
        pulled_model_files_info += f"\t{app_model_filename}\t[@ {dateInfo}]\n"
        
        ### and re-link it back to this folder where it got just pulled back

        # get the full path from shared model filename
        src_filepath = os.path.join(shared_model_folderpath, app_model_filename)
        dst_filepath = os.path.join(app_model_folderpath, app_model_filename)
            
        if os.path.isfile(src_filepath) and not os.path.exists(dst_filepath):
            os.symlink(src_filepath, dst_filepath)
            print(f"\tre-created symlink {app_model_filename} -> {src_filepath} for pulled model")

    if pulled_model_files_count > 0:
        # maintain (create/append to) a readme file for the app_model_folderpath target folder about the pulled Model Files
        readme_pulled_models_filepath = os.path.join(app_model_folderpath, f"{README_FILE_PREFIX}pulled-{model_type.replace('/', '-')}.txt") # translate "/" from grouping map rule into valid readme filename, e.g. "loras/flux" into "loras-flux"

        if not os.path.exists(readme_pulled_models_filepath): # no such readme file exists, so create it
            fileHeader = f"Following model files have been pulled from this directory into the shared_models directory '{shared_model_folderpath}' and re-linked here:\n\n"
            file = open(readme_pulled_models_filepath, 'w') # create the file
            file.writelines(fileHeader) # and write the fileHeader once
            file.writelines(pulled_model_files_info) # and add the pulled Model Files
            file.close()
        else: # readme file already existed from before
            file = open(readme_pulled_models_filepath, 'a') # append to file
            file.writelines(pulled_model_files_info) # and add the pulled Model Files
            file.close()

    return pulled_model_files_count


# helper function called by update_model_symlinks()
def create_model_symlinks(shared_model_folderpath:str, app_model_folderpath:str, model_type:str) -> int:
    # process all files in shared_model_folderpath
    print(f"-> process for creating '{model_type}' app_model file symlinks from their corresponding shared_models sub-folder ...")

    file_symlinks_created_count = 0

    for shared_model_filename in os.listdir(shared_model_folderpath):
        # delete hidden huggingface ".cache" directories in each model directory, as they can exist
        # from possible prior huggingface model downloads.
        # this is a fragment from the hugginface_hub, and can be safely deleted
        shared_model_filepath = os.path.join(shared_model_folderpath, shared_model_filename)
        if shared_model_filename.startswith(".cache") and not os.path.isfile(shared_model_filepath): # hidden ".cache" folder
            shutil.rmtree(shared_model_filepath) # remove the hidden ".cache" huggingface folder
            print(f"Deleted hidden huggingface .cache folder '{shared_model_filepath}")
            continue

        if shared_model_filename.startswith("."):
            continue # skip hidden filenames like ".DS_Store" (on macOS), ".keep" (on GitHub)

        # change the "readme-*.txt" files for the symlinked app folder models
        if shared_model_filename.startswith(README_FILE_PREFIX):
            # create a new readme file for the app_model_folderpath target folder
            readme_synched_filename = os.path.join(app_model_folderpath, shared_model_filename.replace(README_FILE_PREFIX, f'{README_FILE_PREFIX}synced-'))
            os.makedirs(os.path.dirname(readme_synched_filename), exist_ok=True) # ensure parent directory exists
            file = open(readme_synched_filename, 'w')
            file.writelines(f"This folder is synced from the shared_models '{model_type}' models type sub-folder at '{shared_model_folderpath}'.\n\nConsider to put such models there to share them across apps, instead of putting them here!") 
            file.close()

            continue # skip the original "{README_FILE_PREFIX}*.txt" file

        # get the full path from shared model filename
        src_filepath = os.path.join(shared_model_folderpath, shared_model_filename)
        dst_filepath = os.path.join(app_model_folderpath, shared_model_filename) # the dst_filepath always has the SAME filename as the src_filepath

        # skip the small dummy files and not treat them as models
        if os.path.getsize(src_filepath) < 100:
            continue # ZERO (or up to 99 Bytes) sized "put yout model here" files

        print(f"\tprocessing shared '{model_type}' model '{shared_model_filename}' ...")

        if not os.path.isfile(src_filepath): # srcFile is a sub-folder (e.g. "xlabs", or "flux")
            # skip sub-folders, as these require a separate mapping rule to support "flattening" such models
            # for apps which don't find their model_type models in sub-folders
            # add a "model map" for "loras/flux" like the following:
                # Support "Grouping" all FLUX LoRA models into a LoRA "flux" sub-folder for ComfyUI,
                # which again need to be flattened for other apps
                # "loras/flux": {
                #    "ComfyUI": "/models/loras/flux",
                #    "A1111": "/models/Lora", # flatten all "flux" LoRAs here
                #    "Forge": "/models/Lora" # flatten all "flux" LoRAs here
                # }

            print(f"\tthis is a sub-folder which should be mapped with a 'grouping' rule,\n\te.g. ""{model_type}/{shared_model_filename}: { ... }"" in '{SHARED_MODEL_APP_MAP_FILE}'")
            continue

        # create dst_filepath dirs for the parent folder, if needed
        os.makedirs(os.path.dirname(dst_filepath), exist_ok=True)
        
        if os.path.isfile(src_filepath) and not os.path.exists(dst_filepath):
            os.symlink(src_filepath, dst_filepath)
            print(f"\tcreated symlink {shared_model_filename} -> {src_filepath}")
            file_symlinks_created_count = file_symlinks_created_count + 1

    return file_symlinks_created_count


# helper function called from "app.py" via WebUI
#
# this is the main WORKER function running every 5 minutes
# or "on-demand" by the user from the WebUI via app.py:recreate_symlinks_route()->recreate_symlinks()
#
# this function uses following global module vars:
#
# README_FILE_PREFIX (str): "_readme-" <- README files are put in shared model type dirs and also in the app model type dirs,
#   e.g. "_readme-*.txt", "_readme-synced-*.txt", "_readme-pulled-*.txt", "_readme-brokenlinks-*.txt",
#   the "*" is filled with the dir-name of the corresponding model type subfolder of the SHARED_MODELS_DIR (str)
#
# DISABLE_PULLBACK_MODELS (bool) <- set via ENV (True, or False if not present [default])
# LOCAL_DEBUG (bool) <- set via ENV (True, or False if not present [default])
# MAKE_MAPPING_FILES_HIDDEN (bool): default=False (currently only controlled by app code)
#
# SHARED_MODELS_DIR (str): "/workspace/shared_models"
#
# SHARED_MODEL_FOLDERS_FILE (str): "_shared_models_folders.json" (based in SHARED_MODELS_DIR)
# SHARED_MODEL_FOLDERS (dict) <- init from code, then write/read from path SHARED_MODEL_FOLDERS_FILE
#
# APP_INSTALL_DIRS_FILE (str): "_app_install_dirs.json" (based in SHARED_MODELS_DIR)
# APP_INSTALL_DIRS (dict) <- init from code, then write/read from path SHARED_MODEL_FOLDERS_FILE,
# -> synced with global "app_configs" dict for 'app_path' with the use of MAP_APPS (dict)
# MAP_APPS (dict) <- used for mapping "app_configs" (dict) with APP_INSTALL_DIRS (dict)
#
# SHARED_MODEL_APP_MAP_FILE (str): "_shared_models_map.json" (based in SHARED_MODELS_DIR)
# SHARED_MODEL_APP_MAP (dict) <- init from code, then write/read from path SHARED_MODEL_FOLDERS_FILE
def update_model_symlinks():# -> dict:
    try:
        print(f"Processing the master SHARED_MODELS_DIR: {SHARED_MODELS_DIR}")
        if not os.path.exists(SHARED_MODELS_DIR):
            message = f"Folder '{SHARED_MODELS_DIR}' does not exist, please create it first!"
            return jsonify({'status': 'error', 'message': message})

        file_model_symlinks_created_count = 0 # file model symlinks created
        folder_model_symlinks_created_count = 0 # folder model symlinks created
        broken_model_symlinks_count = 0 # broken symlinks to model files and folders
        # "pull-back" model files can be disabled with ENV var "DISABLE_PULLBACK_MODELS=True"
        pulled_model_files_count = 0 # pulled back model files (we not pull back folder models)

        for model_type in SHARED_MODEL_APP_MAP:
            print(f"\n### processing shared '{model_type}' model symlinks for all installed apps ...")

            # check for special LLM folder symlink syntax
            if not model_type.endswith("/*"): # normal file symlink in regular app_model_folderpath folder
                create_folder_symlink = False
                shared_model_folderpath = os.path.join(SHARED_MODELS_DIR, model_type)
            else: # special case for folder symlink
                create_folder_symlink = True
                # strip the "/*" from the model_type (to deal with real folder names), before generating model_folderpaths
                model_type_dirname = model_type.strip("/*")
                shared_model_folderpath = os.path.join(SHARED_MODELS_DIR, model_type_dirname)

            if not os.path.isdir(shared_model_folderpath):
                print(f"shared_model_folderpath '{model_type}' does not exist, skipping")
                continue # skipping non-existant shared_model_folderpath SRC folders
            
            for app_name, app_install_dir in APP_INSTALL_DIRS.items():
                if not os.path.exists(app_install_dir): # app is NOT installed
                    print(f"\n## app '{app_name}' is not installed, skipping")
                    continue # skipping non-installed app_install_dir for this model_type

                print(f"\n## processing for app '{app_name}' ...")

                if not (app_name in SHARED_MODEL_APP_MAP[model_type]):
                    print(f"-> there are no '{model_type}' symlink mappings defined for app '{app_name}', skipping")
                    continue # skipping non-existent app_name mapping for this model_type

                app_model_folderpath = APP_INSTALL_DIRS[app_name] + SHARED_MODEL_APP_MAP[model_type][app_name]
                
                print(f"# Processing the app's '{model_type}' folder '{app_model_folderpath}' ...")

                if not create_folder_symlink: # normal file symlink in regular app_model_folderpath folder

                    # create the app model_type directory, if it doesn't exist
                    os.makedirs(f"{app_model_folderpath}/", exist_ok=True) # append slash to make sure folder is created

                    # first remove all broken/stale links
                    broken_model_type_symlinks_count = remove_broken_model_symlinks(shared_model_folderpath, app_model_folderpath, model_type)
                    
                    if broken_model_type_symlinks_count > 0:
                        readme_filename = f"{README_FILE_PREFIX}brokenlinks-{model_type.replace('/', '-')}.txt" # translate "/" from grouping map rule into valid readme filename, e.g. "loras/flux" into "loras-flux"
                        print(f"-> found and removed #{broken_model_type_symlinks_count} broken link(s) for model type '{model_type}'\nfor more info about which model files symlinks were removed, look into the '{readme_filename}'")
                        # add them to its global counter
                        broken_model_symlinks_count = broken_model_symlinks_count + broken_model_type_symlinks_count

                    if not DISABLE_PULLBACK_MODELS:
                        # then try to pull back local, unlinked app models of this model type (they also get re-shared instantly back)
                        pulled_model_type_files_count =  pull_unlinked_models_back_as_shared_models(shared_model_folderpath, app_model_folderpath, model_type)
                    
                        if pulled_model_type_files_count > 0:
                            readme_filename = f"{README_FILE_PREFIX}pulled-{model_type.replace('/', '-')}.txt"  # translate "/" from grouping map rule into valid readme filename, e.g. "loras/flux" into "loras-flux"
                            print(f"-> found and pulled back #{pulled_model_type_files_count} '{model_type}' model(s) into the corresponding shared_models sub-folder,\nfor more info about which model files were pulled, look into the '{readme_filename}'")
                            # add them to its global counter
                            pulled_model_files_count = pulled_model_files_count + pulled_model_type_files_count

                    # now share (symlink) all models of this type to app model path
                    file_model_type_symlinks_created_count =  create_model_symlinks(shared_model_folderpath, app_model_folderpath, model_type)
                    
                    if file_model_type_symlinks_created_count > 0:
                        # no readme details are tracked about created file symlinks
                        print(f"-> created #{file_model_type_symlinks_created_count} model file symlinks for '{model_type}' model(s)\nyou can see which models are now available in the app's '{app_model_folderpath}'")
                        # add them to its global counter
                        file_model_symlinks_created_count = file_model_symlinks_created_count + file_model_type_symlinks_created_count

                else: # special case for folder symlink with LLM models, which install as folder

                    # e.g. app_model_folderpath = "/workspace/ComfyUI/models/LLM/Meta-Llama-3.1-8B/*"

                    # normally the target mapped/symlinked folder should also use a "/*" suffix,
                    # but that is not stricly required as we can handle that
                    # strip the "/*" from the model-map, to create the a "real" target folder per folder symlink
                    app_model_folderpath = app_model_folderpath.strip("/*")
                    # e.g. app_model_folderpath = "/workspace/ComfyUI/models/LLM/Meta-Llama-3.1-8B"
                    app_model_parent_dir, app_model_foldername = os.path.split(app_model_folderpath)
                    # e.g. app_model_parent_dir = "/workspace/ComfyUI/models/LLM"
                    
                    os.makedirs(os.path.dirname(f"{app_model_parent_dir}/"), exist_ok=True)  # append trailing "/" to make sure the last sub-folder is created
    
                    if os.path.exists(shared_model_folderpath) and not os.path.isfile(shared_model_folderpath) and not os.path.exists(app_model_folderpath):
                        # create a folder symlink
                        os.symlink(shared_model_folderpath, app_model_folderpath, target_is_directory=True)
                        # no readme details are tracked about created folder symlinks
                        print(f"\tcreated a folder symlink {app_model_foldername} -> {shared_model_folderpath}")
                        # the model_type counter for folder models is always 1, as each folder model is its own model_type
                        folder_symlinks_created_count = 1

                        # add this one folder symlink to its global (folder) counter (one-by-one)
                        folder_model_symlinks_created_count = folder_model_symlinks_created_count + folder_symlinks_created_count

        pulled_models_info = "No Pull-Back"
        if not DISABLE_PULLBACK_MODELS: # only show pulled models info, if "pull-back" is not disabled
            pulled_models_info = f"Pulled({pulled_model_files_count})"

        message = f"Links managed:\nFile({file_model_symlinks_created_count}), Folder({folder_model_symlinks_created_count}), Fixed({broken_model_symlinks_count}), {pulled_models_info}"

        print(f"\n\nFinished updating all model type symlinks into their defined app model type directories.")
        print(message)
        print(f"\nFor further customizatons following files were now generated:\n")
        print(f"- README.md: provided help about the other 3 JSON files:\n")
        print(f"- SHARED_MODEL_FOLDERS_FILE '{SHARED_MODEL_FOLDERS_FILE}':\nprovides examples of used 'model_type' directory names for different models.\n")
        print(f"- APP_INSTALL_DIRS_FILE '{APP_INSTALL_DIRS_FILE}':\nprovides examples of used 'app_name': 'app_install_dir' mappings and is used together with the SHARED_MODEL_APP_MAP_FILE.\n")
        print(f"- SHARED_MODEL_APP_MAP_FILE '{SHARED_MODEL_APP_MAP_FILE}':\nprovides examples of used 'model_type' -> 'app_model_dir' mappings.\n")

        print("Model symlinks updated.")

        return jsonify({'status': 'success', 'message': message}) # 'Symlinks (re-)created successfully.'
    
    except Exception as e:
        print(f"ERROR in shared_models:update_model_symlinks() - Exception:\n{str(e)}")

        return jsonify({'status': 'error', 'message': str(e)})

# promote the README
print("To get started with all features of 'shared_models', consult the comprehensive README file")
print('\t"/app/tests/README-SHARED_MODELS.txt"\nIt comes with a Test script and Test data.\n')

print("TESTDATA AND EXPLANATION OF MAPPING EVERYTHING YOU WANT\n")

print('In the folder "/app/tests" you find the following files:')
print('\t- "README-SHARED_MODELS.txt" (this file)')
print('\t- "populate_testdata.sh" (bash script to un-tar and expand all testdata into the "/workspace" folder)')
print('\t- "testdata_shared_models_link.tar.gz" (Testcase #1, read below)')
print('\t- "testdata_stable-diffusion-webui_pull.tar.gz" (Testcase #2, read below)')
print('\t- "testdata_installed_apps_pull.tar.gz" (Testcase #3, read below)\n')

if LOCAL_DEBUG:
    # simulate a RUNPOD environment (e.g. for "/workspace/kohya_ss/setup.sh" or "setup-runpod.sh")
    RUNPOD_POD_ID = "0ce86d9cc8dd"

### setup.sh::
# Check if RUNPOD variable should be set
# RUNPOD=false
# if env_var_exists RUNPOD_POD_ID || env_var_exists RUNPOD_API_KEY; then
#   RUNPOD=true
# fi
#
# # Check if the venv folder doesn't exist
# if [ ! -d "$SCRIPT_DIR/venv" ]; then
#     echo "Creating venv..."
#     python3 -m venv "$SCRIPT_DIR/venv"
# fi
#
# # Activate the virtual environment
# echo "Activating venv..."
# source "$SCRIPT_DIR/venv/bin/activate" || exit 1

# if [[ "$OSTYPE" == "lin"* ]]; then
#   if [ "$RUNPOD" = true ]; then
#     DIR="/workspace/kohya_ss"
#######

### app_configs.py::
#     'bkohya': {
#         'name': 'Better Kohya',
#         'command': 'cd /workspace/bkohya && . ./bin/activate && cd /workspace/kohya_ss && ./gui.sh --listen --port 7860',
#         'venv_path': '/workspace/bkohya',
#         'app_path': '/workspace/kohya_ss',
#         'port': 7860,
#     }
#######