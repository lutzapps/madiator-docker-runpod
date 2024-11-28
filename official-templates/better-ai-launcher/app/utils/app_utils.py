import os
import subprocess
import psutil
import signal
import re
import json
import git
import requests
import traceback
from tqdm import tqdm
import xml.etree.ElementTree as ET

import time
import datetime
import shutil

from utils.app_configs import (DEBUG_SETTINGS, COMMON_SETTINGS, app_configs,
    pretty_dict, init_debug_settings, write_debug_setting, init_app_configs,
    ensure_kohya_local_venv_is_symlinked, read_dict_from_jsonfile, write_dict_to_jsonfile)
from utils.model_utils import (get_sha256_hash_from_file, format_size)
from utils.shared_models import (update_model_symlinks)

INSTALL_STATUS_FILE = '/tmp/install_status.json'

VENV_INFO_FILE = '.venv_info.json' # this file will be put into any successfull installed VENV folder

# lutzapps - support for bkohya gradio url
BKOHYA_LAUNCH_URL = "" # will be captured during run_app('bkohya', ...) from bkohya log
# e.g. https://85f6f17d6d725c6cde.gradio.live

def init_app_status(running_processes:dict) -> dict:
    app_status = {}

    for app_name, config in app_configs.items():
        dirs_ok, message = check_app_directories(app_name, app_configs)
        status = get_app_status(app_name, running_processes)
        install_status = get_install_status(app_name)
        app_status[app_name] = {
            'name': config['name'],
            'dirs_ok': dirs_ok,
            'message': message,
            'port': config['port'],
            'status': status,
            'installed': dirs_ok,
            'install_status': install_status,
            'is_bcomfy': (app_name == 'bcomfy')
        }
    return app_status


def get_bkohya_launch_url() -> str:
    global BKOHYA_LAUNCH_URL
    return BKOHYA_LAUNCH_URL

def is_process_running(pid):
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False

def run_app(app_name, command, running_processes):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, preexec_fn=os.setsid)
    running_processes[app_name] = {
        'process': process,
        'pid': process.pid,
        'log': [],
        'status': 'running'
    }

    # lutzapps - capture the gradio-url for bkohya app
    global BKOHYA_LAUNCH_URL

    BKOHYA_LAUNCH_URL = "" # will be captured during run_app('bkohya', ...) from bkohya log
    # e.g. https://85f6f17d6d725c6cde.gradio.live
    
    for line in process.stdout:
        # wait for gradio-url in bkohya log (the --share option generates a gradio url)
        if app_name == 'bkohya' and BKOHYA_LAUNCH_URL == "":
            gradio_mode = ("--share" in command.lower())
            if gradio_mode and ".gradio.live" in line:
                # get the gradio url from the log line
                # line = '* Running on public URL: https://85f6f17d6d725c6cde.gradio.live\n'
                gradio_url_pattern = r"https://([\w.-]+(?:\.[\w.-]+)+)"

                match = re.search(gradio_url_pattern, line)
                if match:
                    BKOHYA_LAUNCH_URL = match.group(0)  # Full URL, e.g., "https://85f6f17d6d725c6cde.gradio.live"
                    print(f"Public Gradio-URL found in bkohya log: {BKOHYA_LAUNCH_URL}")

            elif not gradio_mode and "127.0.0.1" in line: # only wait for this when gradio_mode = False (=local URL mode)
                port = app_configs[app_name]['port'] # read the configured port from app_configs
                # line = '* Running on local URL: http://127.0.0.1:7864
                BKOHYA_LAUNCH_URL = f"http://127.0.0.1:{port}"
                print(f"Local-URL found in bkohya log: {BKOHYA_LAUNCH_URL}")

        running_processes[app_name]['log'].append(line.strip())
        if len(running_processes[app_name]['log']) > 1000:
            running_processes[app_name]['log'] = running_processes[app_name]['log'][-1000:]
    
    running_processes[app_name]['status'] = 'stopped'

def update_process_status(app_name, running_processes):
    if app_name in running_processes:
        if is_process_running(running_processes[app_name]['pid']):
            running_processes[app_name]['status'] = 'running'
        else:
            running_processes[app_name]['status'] = 'stopped'

# lutzapps - this function controls the UI-State of the Install button in the 'index.html' page
def check_app_directories(app_name, app_configs) -> tuple[bool, str]:
    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."

    venv_path = app_config['venv_path']
    app_path = app_config['app_path']

    # APP/VENV existance and (optionally skipped) size check
    app_verified, app_message = verify_folder_size("APP", app_path, installed_venv_info=None, check_size=False)
    venv_verified, venv_message = verify_folder_size("VENV", venv_path, installed_venv_info=None, check_size=False)

    success = (app_verified and venv_verified)
    message = f"{app_message}\n\n{venv_message}"

    return success, message

def get_app_status(app_name:str, running_processes:dict) -> str:
    if app_name in running_processes:
        update_process_status(app_name, running_processes)
        return running_processes[app_name]['status']
    return 'stopped'

def find_and_kill_process_by_port(port:int) -> bool:
    for conn in psutil.net_connections():
        if conn.laddr.port == int(port):
            try:
                process = psutil.Process(conn.pid)
                for child in process.children(recursive=True):
                    child.kill()
                process.kill()
                return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    return False

def force_kill_process_by_name(app_name:str, app_configs:dict) -> tuple[bool, str]:
    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."

    port = app_config['port']
    killed = find_and_kill_process_by_port(port)

    if killed:
        return True, f"{app_name} processes have been forcefully terminated."
    else:
        return False, f"No running processes found for {app_name} on port {port}."

def get_installed_venv_info(venv_path:str) -> tuple [bool, dict, str]:
    try:
        installed_venv_info_path = os.path.join(venv_path, VENV_INFO_FILE) # hidden venv_info JSON file
        installed_venv_info, error_msg = read_dict_from_jsonfile(installed_venv_info_path) # read the hidden installed_venv_info MANIFEST JSON file
        success = (not installed_venv_info == {} and error_msg == "") # translate to success state

        if success:
            installed_venv_version = installed_venv_info['installed_venv_version']
            message = f"Found venv_info with installed_venv_version='{installed_venv_version}'"
            message += f"\n{pretty_dict(installed_venv_info)}"
        else: # installed_venv_info == {}
            installed_venv_version = 'unknown' # report accordingly
            message = f"Cannot find '{VENV_INFO_FILE}' in VENV folder '{venv_path}', installed_venv_version='{installed_venv_version}'."
            message += f"\nYou may want to consider to delete this possibly older or corrupted installation!"

    except Exception as e:
        success = False
        installed_venv_info = {}
        message = str(e)

    return success, installed_venv_info, message

# lutzapps - new check installation feature
def delete_app_installation(app_name:str, app_configs:dict, progress_callback) -> tuple[bool, str]:
    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."
    
    success = False
    
    try:
        ret_message = f"DELETED Application '{app_name}'"
        progress_callback('install_log', {'app_name': app_name, 'log': f"{ret_message} ..."})

        progress_callback('install_log', {'app_name': app_name, 'log': f"Pull-back local Models from '{app_name}' into shared_models  storage ..."})
        # call update_model_symlinks() to move all local model files into the shared_models folder
        response = update_model_symlinks()
        data = json.loads(response.data.decode()) # response is a flask jsonify response object
        # data is a bytestream which needs to be decode()d and even then the data dict has 'status' and 'message' only as string keys

        message = f"Model sync status: '{data['status']}': {data['message']}"
        progress_callback('install_log', {'app_name': app_name, 'log': f"Status from update_model_symlinks(): {message}"})
        ret_message += f"\n\n{message}\n"

        ### delete APP_PATH
        app_path = app_config['app_path']
        if os.path.exists(app_path):
            progress_callback('install_log', {'app_name': app_name, 'log': f"Deleting Application folder '{app_path}' for app '{app_name}' ..."})
            shutil.rmtree(app_path) # remove APP_PATH from /workspace
            ret_message += f"\napp_path '{app_path}' deleted successfully."
        else:
            ret_message += f"\napp_path '{app_path}' not existed anymore."
            
        ### delete VENV_PATH
        venv_path = app_config['venv_path']
        if os.path.exists(venv_path):
            progress_callback('install_log', {'app_name': app_name, 'log': f"Deleting VENV folder '{venv_path}' for app '{app_name}' ..."})
            shutil.rmtree(venv_path) # remove VENV_PATH from /workspace
            ret_message += f"\nvenv_path '{venv_path}' deleted successfully."
        else:
            ret_message += f"\nvenv_path '{app_path}' not existed anymore."

        success = True

    except Exception as e:
        success = False
        ret_message = str(e)
    
    return success, ret_message


def check_app_installation(app_name:str, app_configs:dict, progress_callback) -> tuple[bool, str]:
    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."

    progress_callback('install_log', {'app_name': app_name, 'log': "Reading VENV environment manifest info ..."})

    venv_path = app_config['venv_path']
    success, installed_venv_info, message = get_installed_venv_info(venv_path) # get the hidden installed_venv_info MANIFEST from the VENV
    progress_callback('install_log', {'app_name': app_name, 'log': message})

    if success:
        installed_venv_version = installed_venv_info['installed_venv_version']
    else: # no installed_venv_info found, exit early
        return False, message

    progress_callback('install_log', {'app_name': app_name, 'log': "Verifying Application folder sizes ..."})

    # APP/VENV existance and (mandatory) size check
    app_path = app_config['app_path']
    app_verified, app_message = verify_folder_size("APP", app_path, installed_venv_info, check_size=True)
    venv_verified, venv_message = verify_folder_size("VENV", venv_path, installed_venv_info, check_size=True)

    is_app_verified = (app_verified and venv_verified)
    verify_message = f"{app_message}\n\n{venv_message}"

    # prepare VERSION INFO from locally saved venv_info installation MANIFEST
    installation_time = installed_venv_info['installation_time']
    refresh_time = installed_venv_info['refresh_time']
    build_info = installed_venv_info['venv_info']['build_info']

    version_message = f"Installed '{installed_venv_version}' version at: {installation_time}\n"
    version_message += f"Last refreshed at: {refresh_time}\n"
    version_message += f"build info: '{build_info}'"

    # check for online updates
    # get the latest_venv_info for this 'installed_venv_version' and check for updated info
    latest_venv_info = get_venv_version_info(installed_venv_version, app_config['available_venvs'])
    latest_build_info = latest_venv_info['build_info'] # get the latest 'build_info' from app_configs MANIFEST

    if not build_info == latest_build_info:
        version_message += f" => Update available: '{latest_build_info}'"

    if is_app_verified:
        message = f"CHECKED '{app_name}'\n\nInstallation was successfully verified:\n\n{verify_message}\n\n{version_message}"
    else:
        message = f"CHECKED '{app_name}'\n\nInstallation did not pass verification:\n\n{verify_message}\n\n{version_message}"

    return is_app_verified, message

# lutzapps - new refresh installation feature
def refresh_app_installation(app_name:str, app_configs:dict, progress_callback) -> tuple[bool, str]:
    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."
    
    success = False
    
    try:
        ret_message = f"REFRESHED Application '{app_name}'"
        progress_callback('install_log', {'app_name': app_name, 'log': f"{ret_message} ..."})

        progress_callback('install_log', {'app_name': app_name, 'log': "Reading VENV environment manifest info ..."})

        venv_path = app_config['venv_path']
        success, installed_venv_info, message = get_installed_venv_info(venv_path) # get the hidden installed_venv_info MANIFEST from the VENV
        progress_callback('install_log', {'app_name': app_name, 'log': message})

        if success:
            installed_venv_version = installed_venv_info['installed_venv_version']
            last_refresh_time = installed_venv_info['refresh_time']
        else: # installed_venv_info == {}
            installed_venv_version = 'unknown'
            last_refresh_time = 'unknown'

        message = f"{app_name} - last refresh time: {last_refresh_time}"
        progress_callback('install_log', {'app_name': app_name, 'log': message})
        ret_message += f"\n\n{message}"

        # check the app_config for 'allow_refresh'
        allow_refresh = app_config['allow_refresh'] # default is that only bkohya opt-out from refresh,
        # until I implement the recursive git pull, or, in the case of 'kohya_ss' via "setup.sh"
        if not allow_refresh:
            ret_message += f"\n'{app_name}' is setup to not auto-refresh currently!"
            progress_callback('install_log', {'app_name': app_name, 'log': ret_message})

            return True, ret_message
        
        progress_callback('install_log', {'app_name': app_name, 'log': f"Pull-back local Models from '{app_name}' into shared_models storage ..."})
        # call update_model_symlinks() to move all local model files into the shared_models folder
        response = update_model_symlinks()
        data = json.loads(response.data.decode()) # response is a flask jsonify response object
        # data is a bytestream which needs to be decode()d and even then the data dict has 'status' and 'message' only as string keys

        message = f"Model sync status: '{data['status']}': {data['message']}"
        progress_callback('install_log', {'app_name': app_name, 'log': f"Status from update_model_symlinks(): {message}"})
        ret_message += f"\n\n{message}"
        
        success, message = clone_application(app_config, installed_venv_version, progress_callback)
        ret_message += f"\n\n{message}"

        if success:
            # update the refresh_time
            refresh_time = "{:%b %d, %Y, %H:%M:%S GMT}".format(datetime.datetime.now())
            installed_venv_info['refresh_time'] = refresh_time
            # and write it back to the hidden venv_info MANIFEST JSON file
            installed_venv_info_path = os.path.join(venv_path, VENV_INFO_FILE) # hidden venv_info JSON file
            success_write = write_dict_to_jsonfile(installed_venv_info, installed_venv_info_path, overwrite=True)
            message = f"refresh time: {refresh_time}"
            progress_callback('install_log', {'app_name': app_name, 'log': message})
            ret_message += f", {message}"


    except Exception as e:
        success = False
        ret_message = str(e)

    return success, ret_message


def update_webui_user_sh(app_name, app_configs):
    app_config = app_configs.get(app_name)
    if not app_config:
        return

    webui_user_sh_path = os.path.join(app_config['app_path'], 'webui-user.sh')
    if not os.path.exists(webui_user_sh_path):
        return

    with open(webui_user_sh_path, 'r') as file:
        content = file.read()

    # Use regex to remove --port and its value
    updated_content = re.sub(r'--port\s+\d+', '', content)

    with open(webui_user_sh_path, 'w') as file:
        file.write(updated_content)

def update_webui_user_sh(app_name, app_configs):
    app_config = app_configs.get(app_name)
    if not app_config:
        return

    webui_user_sh_path = os.path.join(app_config['app_path'], 'webui-user.sh')
    if not os.path.exists(webui_user_sh_path):
        return

    with open(webui_user_sh_path, 'r') as file:
        content = file.read()

    # Use regex to remove --port and its value
    updated_content = re.sub(r'--port\s+\d+', '', content)

    with open(webui_user_sh_path, 'w') as file:
        file.write(updated_content)

def save_install_status(app_name, status, progress=0, stage=''):
    data = {
        'status': status,
        'progress': progress,
        'stage': stage
    }
    try:
        with open(INSTALL_STATUS_FILE, 'r') as f:
            all_statuses = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_statuses = {}
    
    all_statuses[app_name] = data
    
    with open(INSTALL_STATUS_FILE, 'w') as f:
        json.dump(all_statuses, f)

def get_install_status(app_name) -> dict:
    try:
        with open(INSTALL_STATUS_FILE, 'r') as f:
            all_statuses = json.load(f)
        return all_statuses.get(app_name, {'status': 'not_started', 'progress': 0, 'stage': ''})
    except (FileNotFoundError, json.JSONDecodeError):
        return {'status': 'not_started', 'progress': 0, 'stage': ''}

# lutzapps - fastversion for ownload_and_unpack_venv()
import subprocess

# currently not used
# import threading
# from queue import Queue, Empty
# from concurrent.futures import ThreadPoolExecutor

import time

### lutzapps
# helper function for threaded STDOUT/STDERR streaming into QUEUES for later consumption
# currently not used

# this the called by the thread_output_reader
# def enqueue_output(file, queue):
#     for line in iter(file.readline, b''): # read the streaming file until the end (byte '')
#         queue.put(line.decode('utf-8')) # and put it in queue as UTF-8 string (and not as byte array)

# def read_open_pipes(process):
#     with ThreadPoolExecutor(2) as pool:
#         queue_stdout, queue_stderr = Queue(), Queue()

#         pool.submit(enqueue_output, process.stdout, queue_stdout)
#         pool.submit(enqueue_output, process.stderr, queue_stderr)

#         while True:
#             if process.poll() is not None and queue_stdout.empty() and queue_stderr.empty():
#                 break # exit loop when process alive but not have any output in STDOUT or STDERR

#             out_line = err_line = ''

#             try:
#                 out_line = queue_stdout.get_nowait()
#             except Empty:
#                 pass
#             try:
#                 err_line = queue_stderr.get_nowait()
#             except Empty:
#                 pass

#             yield (out_line.rstrip(), err_line.rstrip())

#

def download_and_unpack_venv(app_name:str, venv_version:str, progress_callback) -> tuple[bool, str]:
    # load the latest configured DEBUG_SETTINGS from the stored setting of the DEBUG_SETTINGS_FILE
    init_debug_settings() # reload latest DEBUG_SETTINGS
    # as this could overwrite the APP_CONFIGS_MANIFEST_URL, we reload the app_configs global dict
    # from whatever Url is now defined
    # debug_settings can also overwrite the used VENV ('official' or 'latest'),
    # without the need to overwrite the whole app_config section
    init_app_configs() # reload lastest app_configs dict

    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."

    venv_path = app_config['venv_path']

    if (venv_version == None or venv_version == 'undefined' or venv_version == ''): # if still not have a venv_version,
        venv_version = app_config['venv_version_default'] #  use the default version for this app from its app_config
        print(f"Select DEFAULT '{venv_version}' VENV environment from app config")        

    # get the current venv_version_info for installation
    venv_version_info = get_venv_version_info(venv_version, app_config['available_venvs'])
    
    message = f"Using venv_info='{venv_version}' for installation of '{app_name}'"
    message += f"\n{pretty_dict(venv_version_info)}"
    print(message)

    base_download_url = COMMON_SETTINGS['base_download_url'] # base-url used for relative download_urls

    relative_download_url = venv_version_info['download_url']
    if not "://" in relative_download_url: # if download_url is a relative url
        print(f"using base_download_url: {base_download_url}")
        download_url = os.path.join(base_download_url, relative_download_url) # then make it an absolute url

    print(f"downloading VENV from download_url: {download_url}")

    archive_size_bytes = venv_version_info['archive_size_bytes']
    uncompressed_size_bytes = venv_version_info['venv_uncompressed_size_kb'] * 1024
    venv_version_info_sha256_hash = venv_version_info["sha256_hash"].lower()
    
    tar_filename = os.path.basename(download_url)
    workspace_dir = '/workspace'
    downloaded_file = os.path.join(workspace_dir, tar_filename)

    write_debug_setting('last_app_name', app_name)
    write_debug_setting('used_venv_version', venv_version)
    write_debug_setting('used_tar_filename', tar_filename)
    write_debug_setting('used_download_url', download_url)

    try:
        # VENV existance and (mandatory) size check
        venv_verified = False

        venv_found, installed_venv_info, message = get_installed_venv_info(venv_path) # get the hidden installed_venv_info MANIFEST from the VENV
        if venv_found and venv_version == installed_venv_info['installed_venv_version']:
            # verify, if the existing VENV can be re-used
            venv_verified, message = verify_folder_size("VENV", venv_path, installed_venv_info, check_size=True)
            progress_callback('install_log', {'app_name': app_name, 'log': message})

            if not venv_verified:
                # installed VENV did not pass verification
                error_message = f"Existing VENV '{app_name}' did not pass verification: {message}!"
                error_message += f"\nDeleting this unverified VENV ..."
                progress_callback('install_log', {'app_name': app_name, 'log': error_message})
                shutil.rmtree(venv_path) # delete unverified VENV_PATH

        else: # no existing VENV found, or the VENV is not matching with requested 'venv_version'
            if venv_found: # existing VENV, but version mismatch
                # installed_venv_info MANIFEST not found or it does not match with the requested 'venv_version' to install
                error_message = f"Existing VENV '{app_name}' found, but it has no MANIFEST file, or the installed venv version does not match with the requested version '{venv_version}'!"
                error_message += f"\nDeleting this stale VENV ..."
                progress_callback('install_log', {'app_name': app_name, 'log': error_message})
                shutil.rmtree(venv_path) # delete stale VENV_PATH
        
        if venv_verified:
            progress_callback('install_log', {'app_name': app_name, 'log': 'Reusing existing verified VENV, skipping to App Cloning stage ...'})

            # the APP path should NOT exist, otherwise we should not have been called via Setup (if both VENV and APP path existed)
            success, message = clone_application(app_config, venv_version, progress_callback)

            if success:
                ### VENV INFO Stage - Write venv info for reference        
                # write the hidden venv_info JSON file for later app verification with check_app_installation() UI function
                progress_callback('install_log', {'app_name': app_name, 'log': 'APP setup complete. Updating APP manifest ...'})

                installation_time = "{:%b %d, %Y, %H:%M:%S GMT}".format(datetime.datetime.now())
                refresh_time = installation_time # refresh time is install time

                # update existing installed VENV MANIFEST
                installed_venv_info['installation_time'] = installation_time
                installed_venv_info['refresh_time'] = refresh_time

                installed_venv_info_path = os.path.join(venv_path, VENV_INFO_FILE) # hidden venv_info JSON file
                success = write_dict_to_jsonfile(installed_venv_info, installed_venv_info_path, overwrite=True) # write the hidden venv_info into the VENV folder of the app

                progress_callback('install_log', {'app_name': app_name, 'log': f"Installation complete. Refresh page to start the app '{app_name}'"})
                save_install_status(app_name, 'completed', 100, 'Completed')
                message = "Application installed successfully, existing, verified Virtual Environment was re-used"
                progress_callback('install_complete', {'app_name': app_name, 'status': 'success', 'message': message})

                return True, message


        ### DOWNLOAD Stage (no existing VENV)

        save_install_status(app_name, 'in_progress', 0, 'Downloading')
        progress_callback('install_log', {'app_name': app_name, 'log': f'Downloading {archive_size_bytes / (1024 * 1024):.2f} MB ...'})

        start_time_download = time.time()

        # use existing local cached TAR file
        if os.path.exists(downloaded_file):
            write_debug_setting('used_local_tarfile', True) # indicate using cached TAR file
            progress_callback('install_log', {'app_name': app_name, 'log': f"Using cached local archive '{downloaded_file}'."})

            # fill the progress bar to 100%
            progress_callback('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Download Complete'})

        else:
            write_debug_setting('used_local_tarfile', False) # indicate no cached TAR file found

            try: ### download with ARIA2C

                # -x (--max-connection-per-server=) 16 
                ### bash version with progress file
                ### aria2c --max-connection-per-server=16 --max-concurrent-downloads=16 --split=16 --summary-interval=1 https://better.s3.madiator.com/bkohya.tar.gz --dir=/workspace > /tmp/download-progress.txt &
                ### View file with "tail --follow /tmp/download-progress.txt" or "tail -n 2 /tmp/download-progress.txt"

                ### python version with stdout
                ### aria2c -x 16 -j 16 -s 16 --summary-interval=1 https://better.s3.madiator.com/bkohya.tar.gz --dir=/workspace

                # start aria2c with 16 download threads, write summary every 1 sec to stdout for progress indicator
                cmd_line = f"aria2c --max-connection-per-server=16 --max-concurrent-downloads=16 --split=16 --summary-interval=1 {download_url} --dir={workspace_dir}"
                print(f"start DOWNLOAD with cmd '{cmd_line}'")

                cmd = cmd_line.split(" ") # the cmdline args need to set a list of strings

                # start the download
                # download_process = subprocess.Popen(cmd_line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                # download_isrunning = (download_process and download_process.poll())

                print(f"stage: 'Downloading', launching cmd: '{cmd_line}'")
                with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as download_process:
                    # this is the main loop during download
                    for line in download_process.stdout:
                        download_line = line.rstrip()

                        # capture download progress
                        # tail -n 6 /tmp/download-progress.txt
                        # During Download (last 6 lines):
                        # --->
                        # *** Download Progress Summary as of Sat Nov  2 17:23:16 2024 *** 
                        # ===============================================================================
                        # [#cd57da 2.1GiB/4.0GiB(53%) CN:16 DL:1.9MiB ETA:16m19s]
                        # FILE: /worksapce/bkohya-latest.tar.gz
                        # -------------------------------------------------------------------------------
                        # <---

                        # When ready (last 6 lines):
                        # Download Results:
                        # --->
                        # gid   |stat|avg speed  |path/URI
                        # ======+====+===========+=======================================================
                        # cd57da|OK  |   1.6MiB/s|/workspace/bkohya-latest.tar.gz

                        # Status Legend:
                        # (OK):download completed.
                        # <---

                        download_running_line_pattern = r"\[#(\w+)\s+(\d+\.?\d*)\s*([GMK]iB)/(\d+\.?\d*)\s*([GMK]iB)\((\d+)%\)\s+CN:(\d+)\s+DL:(\d+\.?\d*)\s*([GMK]iB)\s+ETA:(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?\]"
                        
                        # download_finished_line = "cd57da|OK  |   1.6MiB/s|/workspace/bkohya-latest.tar.gz"
                        download_finished_line_pattern = r"([a-fA-F0-9]{6})\|(\w+)\s*\|\s*([\d.]+[GMK]iB/s)\|(.+)"

                        # try to find the download_running_line_pattern
                        match = re.match(download_running_line_pattern, download_line)
                        if match: # download_running_line_pattern
                            gid = match.group(1)                    # e.g., "cd57da"
                            downloaded_size_value = match.group(2)  # e.g., "2.1"
                            downloaded_size_unit = match.group(3)   # e.g., "GiB"
                            total_size_value =  match.group(4)      # e.g., "4.0" (this could replace the 'archive_size_bytes' from the manifest)
                            total_size_unit = match.group(5)        # e.g., "GiB" (with calculation to bytes, but not sure if its rounded)
                            percentage = int(match.group(6))        # e.g., "53"
                            connection_count = int(match.group(7))  # e.g., "16"
                            download_rate_value = match.group(8)    # e.g., "1.9"
                            download_rate_unit = match.group(9)     # e.g., "MiB"
                            eta_hours = int(match.group(10) or 0)   # e.g., None if no hours present, or the hour value if present
                            eta_minutes = int(match.group(11) or 0) # e.g., "16" or None
                            eta_seconds = int(match.group(12) or 0) # e.g., "19" or None

                            # format "2.1GiB" as "2.1 GiB"
                            downloaded_size_formatted = f"{downloaded_size_value} {downloaded_size_unit}"

                            # format "1.9MiB" as "1.9 MiB/s"
                            download_rate_formatted = f"{download_rate_value} {download_rate_unit}/s"

                            # calculate eta in seconds
                            eta = eta_hours * 3600 + eta_minutes * 60 + eta_seconds

                            ### original code
                            #speed = downloaded_size_bytes / elapsed_time # bytes/sec
                            #percentage = (downloaded_size_bytes / archive_size_bytes) * 100
                            #eta = (archive_size_bytes - downloaded_size_bytes) / speed if speed > 0 else 0 # sec
                            
                            progress_callback('install_progress', {
                                'app_name': app_name,
                                'percentage': percentage,
                                'speed': download_rate_formatted, # f"{speed / (1024 * 1024):.2f} MiB/s",
                                'eta': f"{eta:.0f}",
                                'stage': 'Downloading',
                                'downloaded': downloaded_size_formatted # f"{downloaded_size_bytes / (1024 * 1024):.2f} MB"
                            })

                        else: # then try to find the download_finished_line_pattern
                            match = re.match(download_finished_line_pattern, download_line)
                            if match: # download_finished_line_pattern
                                finish_gid = match.group(1) # cd57da
                                status = match.group(2) # OK
                                speed = match.group(3) # 1.6MiB/s (GiB/s, MiB/s, or KiB/s)
                                finish_downloaded_file = match.group(4) # /workspace/bkohya.tar.gz

                                if finish_gid == gid and finish_downloaded_file == download_url:
                                    download_isrunning = False # exit the downlood_isrunning loop

                            # else any other line in stdout (which we not process)

                download_process.wait() # let the process finish
                rc = download_process.returncode # and get the return code

                # delete temporary ".aria2" file 
                if os.path.exists(f"{tar_filename}.aria2"):
                    os.remove(f"{tar_filename}.aria2")

                # fill the progress bar to 100%
                progress_callback('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Download Complete'})

                total_duration_download = f"{datetime.timedelta(seconds=int(time.time() - start_time_download))}"
                write_debug_setting('total_duration_download', total_duration_download)
                print(f"download did run {total_duration_download} for app '{app_name}'")

                if rc != 0:
                    error_message = f"Download failed: {download_process.stderr.read() if download_process.stderr else 'Unknown error'}"
                    progress_callback('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
                    save_install_status(app_name, 'failed', 0, 'Failed')

                    return False, error_message

                progress_callback('install_log', {'app_name': app_name, 'log': 'Download complete. Proceeding to verify downloaded archive ...'})

            except Exception as e:
                error_msg = f"ERROR in download_and_unpack_venv():download with ARIA2C\ncmdline: '{cmd_line}'\nException: {str(e)}"
                print(error_msg)

                error_message = f"Downloading VENV failed: {download_process.stderr.read() if download_process.stderr else 'Unknown error'}"
                progress_callback('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
                save_install_status(app_name, 'failed', 0, 'Failed')

                return False, error_message


        ### VERIFY Download stage (non-existing TAR file)
        if not os.path.exists(downloaded_file):
            error_message = f"Downloading VENV archive failed, file '{downloaded_file}' does not exist, canceling Setup!\nPlease provide this TAR file, refresh the page, and try again!"
            progress_callback('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
            save_install_status(app_name, 'failed', 0, 'Download')

            return False, error_message
            

        ### VERIFY Download stage (existing TAR file)
        #
        # Create TAR from the VENV current directory:
        #   IMPORTANT: cd INTO the folder you want to compress, as we use "." for source folder,
        #   to avoid having the foldername in the TAR file !!!
        #   PV piping is "nice-to-have" and is only used for showing "Progress Values" during compressing
        #
        #       cd /workspace/bkohya
        #       #tar -czf | pv > /workspace/bkohya-latest.tar.gz . (not the smallest TAR)#
        #       tar -cvf - . | gzip -9 - | pv > /workspace/bkohya-latest.tar.gz
        #
        #   afterwards create the SHA256 hash from this TAR with
        #        shasum -a 256 /workspace/bkohya-latest.tar.gz
        #
        #   report the size of the TAR via 'ls bkohya-latest.tar.gz -la' (in Bytes)
        #   also report the uncompressed size (in KBytes) from the current VENV directory via 'du bkohya -sk',
        #   we need that as the 100% base for the progress indicators when uncompressing the TAR


        # verify the downloaded TAR file against its SHA256 hash value from the manifest

        progress_callback('install_log', {'app_name': app_name, 'log': f"Starting SHA256 Verification of archive '{downloaded_file}' ..."})

        file_verified = False

        print(f"getting SHA256 Hash for '{downloaded_file}'")
        successfull_hash_generation, file_sha256_hash = get_sha256_hash_from_file(downloaded_file)
        
        if successfull_hash_generation and file_sha256_hash.lower() == venv_version_info_sha256_hash.lower():
            file_verified = True
            message = f"Downloaded file '{os.path.basename(downloaded_file)}' was successfully (SHA256) verified."
            print(message)
        
        else:
            if successfull_hash_generation: # the generated SHA256 file hash did not match against the metadata hash 
                error_message = f"The downloaded file '{os.path.basename(downloaded_file)}' has DIFFERENT \nSHA256: {file_sha256_hash} as in the manifest\nFile is possibly corrupted and was DELETED!"
                print(error_message)

                os.remove(downloaded_file) # delete corrupted, downloaded file
           
            else: # NOT successful, the hash contains the Exception
                error_msg = file_sha256_hash
                error_message = f"Exception occured while generating the SHA256 hash for '{downloaded_file}':\n{error_msg}"
                print(error_message)

        if not file_verified:
            progress_callback('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
            save_install_status(app_name, 'failed', 0, 'Failed')

            return False, error_message

        progress_callback('install_log', {'app_name': app_name, 'log': 'Verification completed. Start unpacking ...'})

        ### Decompression Stage (Unpacking the downloaded VENV)
        start_time_unpack = time.time()

        # Ensure the venv directory exists
        os.makedirs(f"{venv_path}/", exist_ok=True) # append trailing "/" to make sure the last sub-folder is created

        # Unpack the tar.gz archive file
        progress_callback('install_progress', {'app_name': app_name, 'percentage': 0, 'stage': 'Unpacking'})


        ### getting STATISTICS stage
        # first we need the statistics of the tar.GZ file (statically or with the help of "gzip"
        #
        # NOTE: if we put this info already in the XML manifest, we could even skip the STATISTICS stage
        # but it is very fast anyway
        # we could also add a SHA256 hash to the XML manifest and verify the downloaded tar against this hash
        # same as we already do for model file downloads

        # VENV uncompressed sizes (in bytes) of the TAR GZ files:
        # 'bcomfy': 6155283197
        # 'ba1111': 6794355530
        # 'bforge': 7689838771 
        # 'bkohya': 12192767148

        ### NOTE: as it turns out GZIP has problems with files bigger than 2 or 4 GB due to internal field bit restrictions

        # cmd_line = f"gzip -l {downloaded_file}" # e.g. for 'ba1111.tar.gz'

        # cmd = cmd_line.split(" ") # the cmdline args need to set a list of strings

        # compressed_size_bytes = 0
        # uncompressed_size_bytes = 0

        # line_number = 0
        # unexpected_line_results = ""
        # compression_header_line =   "         compressed        uncompressed  ratio uncompressed_name" # header line#0
        # compression_info_line =     "         3383946179          2543929344 -33.1% /workspace/ba1111.tar" # info line#1
        # # or can be also            "         6295309068          3707578368 -69.8% /workspace/bkohya.tar"

        # compression_info_line_pattern = r"^\s*(\d+)\s+(\d+)\s+([+-]?\d+\.?\d*%)\s+(.+)"

        # print(f"stage: 'Statistics', launching cmd: '{cmd_line}'")
        # with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as statistics_process:
        #     # compressed uncompressed  ratio uncompressed_name
        #     # 3383946179   2543929344 -33.1% /workspace/ba1111.tar
        #     for line in statistics_process.stdout:
        #         if line_number == 0: # compression_header line
        #             compression_header_line = line.rstrip()
        #             print(compression_header_line)

        #             if "uncompressed" in compression_header_line: # verify header line
        #                 line_number += 1
        #                 continue # skip this header line
        #             else: # unexpected result
        #                 unexpected_line_results = compression_header_line
        #         elif line_number == 1 and unexpected_line_results == "": # compression_info line
        #             compression_info_line = line.rstrip()
        #             print(compression_info_line)
                    
        #             # decode and extract compression info for statistics in main Decompression later
        #             match = re.match(compression_info_line_pattern, compression_info_line)
        #             if match:
        #                 compressed_size_bytes = int(match.group(1)) # 3383946179
        #                 uncompressed_size_bytes = int(match.group(2)) # 2543929344 or 0
        #                 if uncompressed_size_bytes == 0: # TAR file has no compression at all
        #                     uncompressed_size_bytes = compressed_size_bytes # use the compressed_size_bytes also as uncompressed_size_bytes
        #                 compression_ratio = match.group(3) # -33.1% or 0.0%
        #                 uncompressed_name = match.group(4) # ba1111.tar (note: the name here is without .gz)

        #         else: # more unexpected lines
        #             unexpected_line_results += f"\n{line.rstrip()}"

        #         line_number += 1

        # statistics_process.wait() # let the process finish
        # rc = statistics_process.returncode # and get the return code

        # if (rc != 0) or (not unexpected_line_results == ""):
        #     error_message = f"GetCompressionInfo failed: {proc.stderr.read() if statistics_process.stderr else 'Unknown error'}\n{unexpected_line_results}"
        #     progress_callback('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
        #     save_install_status(app_name, 'failed', 0, 'Failed')

        #     return False, error_message
        

        ### UNPACKING Stage
        try: # unpack with PIGZ, a parallel version of gzip. Although it only uses a single thread for decompression,
            # it starts 3 additional threads for reading, writing, and check calculation

            ### python version with stdout
            ### pigz -dc /workspace/bkohya.tar.gz | pv | tar xf -

            # PIGZ always outputs/extracts to CURRENT directory!
            # So make sure to change to the apps venv directory first!!!

            # start PIGZ and use PV for progress data (could play with much more PV options)
            cmd_line = f"cd {venv_path} && pigz -dc {downloaded_file} | pv | tar xf -" # note the last "-" for STDOUT dir for TAR extraction

            # to SEE the PV values from code, when to setup the 3 Cmds and Pipes manually in subprocess Popen

            pigz_cmd_line = f"pigz -dc {downloaded_file}" # the TAR/GZ file goes in thru STDIN
            pigz_cmd = pigz_cmd_line.split(" ")
            pigz_process = subprocess.Popen(pigz_cmd, stdout=subprocess.PIPE, text=True) # and passed to PV
            
            # --force output (even if process has no termnial), progress-info is always passed thru STDERR, which we also pipe as text)
            pv_process = subprocess.Popen(["pv", "--force"], stdin=pigz_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # capture decompression progress
            # tail -n 2 /tmp/decompression-progress.txt
            # During Decompression (last 2 lines):
            # --->
            # 11.5GiB 0:03:02 [64.2MiB/s] [                <=>                               ]
            # 11.5GiB 0:03:06 [63.0MiB/s] [            <=>                                   ]
            # <---

            # When ready (last 2 lines):
            # --->
            # ???
            # ???
            # <---

            # decompression_running_line = "11.5GiB 0:03:02 [64.2MiB/s] [                <=>                               ]"
            decompression_running_line_pattern = r"(\d+\.?\d*)\s*([GMK]iB)\s+(\d+:\d{2}:\d{2})\s+\[(\d+\.?\d*)\s*([GMK]iB/s)\]\s+\[([<=>\s]+)\]"

            print(f"stage: 'Unpacking', launching cmd: '{cmd_line}'")
            # When you pass shell=True, Popen expects a single string argument, not a cmd and arg string-list.
            # with subprocess.Popen(cmd_line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, text=True) as decompression_process:
            # the "-" in the TAR cmd uses STDOUT as file output, which it gets thru the pipe from PIGZ, STDERR has the piped stderr from PV, CWD id the path to the VENV folder the TAR should extract to
            with subprocess.Popen(["tar", "xf", "-"], stdin=pv_process.stdout, stdout=subprocess.PIPE, stderr=pv_process.stderr, text=True, cwd=venv_path) as decompression_process:
                #stdout_piped, stderr_piped = decompression_process.communicate()

                # close the piped stdouts
                # pigz_process.stdout.close()
                # pv_process.stdout.close()

                for line in pv_process.stderr:

                    decompression_line = line.rstrip()

                    print(decompression_line) # show the progress in the log

                    # try to find the decompression_running_line_pattern
                    match = re.match(decompression_running_line_pattern, decompression_line)
                    if match: # decompression_running_line_pattern
                        decompression_size_bytes = float(match.group(1))# e.g. "11.5"
                        decompression_size_unit = match.group(2)        # e.g. "GiB"
                        decompression_time_string = match.group(3)      # e.g. "0:03:02"
                        decompression_speed = match.group(4)            # e.g. "64.2"
                        decompression_speed_unit = match.group(5)       # e.g. "MiB/s"
                        progress_bar = match.group(6)                   # e.g. "<=>"

                        # calculate the decompression_size in bytes
                        if decompression_size_unit == "KiB":
                            decompression_size_bytes *= 1024
                        elif decompression_size_unit == "MiB":
                            decompression_size_bytes *= 1024 * 1024
                        elif decompression_size_unit == "GiB":
                            decompression_size_bytes *= 1024 * 1024 * 1024

                        # calculate percentage based on total TAR "compressed_size_bytes", we extracted from the previous 'STATISTICS' stage
                        percentage = min(int((decompression_size_bytes / uncompressed_size_bytes) * 100), 100)

                        # format "64.2MiB/s" as "64.2 MiB/s"
                        decompression_speed_formatted = f"{decompression_speed} {decompression_speed_unit}"

                        # no ETA in 'Unpacking' stage (currently)
                        # but we could "calculate" ETA from the info we have or add some "PV" options to get it easier

                        progress_callback('install_progress', {
                            'app_name': app_name,
                            'percentage': percentage,
                            'stage': 'Unpacking',
                            'processed': decompression_speed_formatted
                        })

                        # another summary line (every 1s) for the install_log
                        decompression_progress_details = f"{decompression_time_string} {percentage}% {int(decompression_size_bytes / (1024 * 1024))} / {int(uncompressed_size_bytes / (1024 * 1024))} MiB @ {decompression_speed} {decompression_speed_unit}"
                        
                        progress_callback('install_log', {'app_name': app_name, 'log': f"Unpacking: {decompression_progress_details}"})
                        # index.html: div id="install-logs-bkohya" added line-per-line
                        # index.html: speedDisplay.textContent = `Processed: ${data.processed} / ${data.total} files`;

                # else: # then try to find the decompression_finish_line_pattern
                #     match = re.match(decompression_finish_line_pattern, decompression_line)
                #     if match: # decompression_finish_line_pattern
                #         finish_gid = match.group(1) # cd57da
                #         status = match.group(2) # OK
                #         speed = match.group(3) # 1.6MiB/s (GiB/s, MiB/s, or KiB/s)
                #         finish_downloaded_file = match.group(4) # /workspace/bkohya.tar.gz

                #         if finish_gid == gid and finish_downloaded_file == download_url:
                #             decompression_isrunning = False # exit the decompression_isrunning loop

                    # else any other line in stdout (which we not process)

        except Exception as e:
            error_msg = f"ERROR in download_and_unpack_venv():\ncmdline: '{cmd_line}'\nException: {str(e)}"
            print(error_msg)

        decompression_process.wait() # let the process finish
        rc = decompression_process.returncode # and get the return code

        # fill the progress bar to 100%
        progress_callback('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Unpacking Complete'})

        total_duration_unpack = f"{datetime.timedelta(seconds=int(time.time() - start_time_unpack))}"
        write_debug_setting('total_duration_unpack', total_duration_unpack)
        print(f"unpack did run {total_duration_unpack} for app '{app_name}'")

        if rc != 0:
            error_message = f"Unpacking failed: {decompression_process.stderr.read() if decompression_process.stderr else 'Unknown error'}"
            progress_callback('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
            save_install_status(app_name, 'failed', 0, 'Failed')

            return False, error_message
        
        progress_callback('install_log', {'app_name': app_name, 'log': 'Unpacking of VENV complete. Proceeding to VENV verification ...'})

        # VENV existance and (mandatory) size check after Unpacking
        venv_verified, message = verify_folder_size("VENV", venv_path, installed_venv_info, check_size=True)

        # Clean up the downloaded TAR file
        progress_callback('install_log', {'app_name': app_name, 'log': 'Cleaning up ...'})

        # debug with local TAR
        if venv_verified and DEBUG_SETTINGS["delete_tar_file_after_download"]: # this is the default, but can be overwritten
            os.remove(downloaded_file) # only remove the TAR file if VENV was fully extracted, otherwise reuse it in next retry to install the VENV again

        progress_callback('install_log', {'app_name': app_name, 'log': 'VENV Verification complete. Proceeding to APP setup ...'})


        ### APPLICATION SETUP - Clone the Github App repository
        success, message = clone_application(app_config, venv_version, progress_callback)
        if not success:
            return False, message


        ### VENV INFO Stage - Write venv info for reference        
        # write the hidden venv_info JSON file for later app verification with check_app_installation() UI function
        progress_callback('install_log', {'app_name': app_name, 'log': 'APP setup complete. Saving APP manifest ...'})

        venv_info_path = os.path.join(venv_path, VENV_INFO_FILE) # hidden venv_info JSON file
        # get the current venv_version_info for this installation
        venv_version_info = get_venv_version_info(venv_version, app_config['available_venvs'])
        # replace the relative download url from the manifest into the used absolute download url for reference
        venv_version_info['download_url'] = download_url # this is the absolute download_url
        installation_time = "{:%b %d, %Y, %H:%M:%S GMT}".format(datetime.datetime.now())
        refresh_info = venv_version_info['build_info'] # refresh time is build time

        installed_venv_info = {
            'installed_venv_version': venv_version,
            'installation_time': installation_time,
            'refresh_time': refresh_info,
            'venv_info': venv_version_info
        }

        success = write_dict_to_jsonfile(installed_venv_info, venv_info_path, overwrite=True) # write the hidden venv_info into the VENV folder of the app

        progress_callback('install_log', {'app_name': app_name, 'log': f"Installation complete. Refresh page to start the app '{app_name}'"})
        save_install_status(app_name, 'completed', 100, 'Completed')
        message = "Application and Virtual Environment installed successfully."
        progress_callback('install_complete', {'app_name': app_name, 'status': 'success', 'message': message})

        return True, message

    except Exception as e:
        error_message = f"Installation failed: {str(e)}\n{traceback.format_exc()}"
        save_install_status(app_name, 'failed', 0, 'Failed')
        progress_callback('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
        return False, error_message

# lutzapps - VENV/APP folder existance and optionally size check
# If the 'check_size' param is passed as True, then calculate the installed VENV/APP folder sizes
# against expected sizes from the passed 'installed_venv_info' dict, which was read from a hidden MANIFEST file in the VENV folder
# Such size checks can take some annoying 30 seconds (for all installed apps), and blocking the 'index.html' page!
# So for check_app_directories() the size check is skipped, and a "shallow" fast check is done.
# For all other use cases (during Installation time before the "Downloading" and after the "Expanding" stage,
# and during Check or Refresh Application) size checks against 'installed_venv_info' are done.
def verify_folder_size(folder_type:str, folder_path:str, installed_venv_info:dict=None, check_size:bool=False) -> tuple[bool, str]:
    message = f"{folder_type} path: '{folder_path}' - "

    is_folder_verified = False

    try:
        if os.path.exists(folder_path):
            message += f"folder exists.\n"

            if not check_size:
                return True, f"Folder size check for '{folder_path}' was skipped."

            if folder_type.lower() == 'venv':
                expected_folder_size_kb = installed_venv_info['venv_info']['venv_uncompressed_size_kb'] # that is the baseline 'venv_path' folder size
            elif folder_type.lower() == 'app':
                expected_folder_size_kb = installed_venv_info['venv_info']['minimum_app_size_kb'] # that is the baseline 'app_path' folder size
            else: # fatal error, catch early and leave
                return False, f"unexpected folder type: '{folder_type}'"
            
            if not COMMON_SETTINGS[f'verify_{folder_type.lower()}_size']: # set in app_configs and overwriteable in DEBUG_SETTINGS
                return True, f"{folder_type} folder size check for '{folder_path}' was skipped via settings."

            message += f"expected minimum {folder_type} size: {format_size(expected_folder_size_kb * 1024)}"

            current_folder_size_info_kb = subprocess.check_output(['du', '-sk'], cwd = folder_path).decode('utf-8') # decode the byte-coded result
            # current_folder_size_info_kb = "6394964\t.\n"
            folder_size_info_pattern = r"^(\d+)\t\." # '.' is the CWD dir name

            match = re.match(folder_size_info_pattern, current_folder_size_info_kb)
            if match:
                current_folder_reported_size_kb = int(match.group(1)) # e.g. "6394964" (folder tree size of CWD '.')

                # percentage (int) factor the 'verify_sizes' for app_path and venv_path are allowed to vary
                verify_tolerance_percent = int(COMMON_SETTINGS['verify_tolerance_percent'])

                if (current_folder_reported_size_kb * (100 + verify_tolerance_percent) / 100) < expected_folder_size_kb: # folder is smaller than its minimum expected size from its installed/saved venv_info manifest
                    message += f" > {format_size(current_folder_reported_size_kb * 1024)} current size (+{verify_tolerance_percent}%) - {folder_type} verification failed!"

                    if COMMON_SETTINGS[f'delete_unverified_{folder_type.lower()}_path']: # set in app_configs and overwriteable in DEBUG_SETTINGS
                        shutil.rmtree(folder_path) # delete non-verified VENV_PATH / APP_PATH

                else: # folder size is at least the expected_folder_size_kb defined in installed_venv_info
                    is_folder_verified = True
                    message += f" <= {format_size(current_folder_reported_size_kb * 1024)} current size (+{verify_tolerance_percent}%) - {folder_type} verification passed."
        else:
            message += f"folder does not exists, {folder_type} verification failed!"

    except Exception as e:
        message = str(e)

    #print(message)    
    return is_folder_verified, message

def get_venv_version_info(venv_version:str, available_venvs:list) -> dict:
    venv_version_info = {}
    # try to find the selected venv_version in the 'available_venvs' of the app
    for venv in available_venvs: # get the venvs array of the app
        if venv_version == venv['version']: # if found the selected version, then
            venv_version_info = venv # use the ONE selected venv as Dictionary (and not as list)
            break # exit the for-loop

    return venv_version_info

### installing the App from GITHUB
# Clone the repository, if it doesn't already exist
# refresh the repository, if it is already installed
# recursive cloning/refreshing of git sub-modules supported (e.g. kohya_ss)
# special support for "bcomfy" and custom_nodes installation:
# clone/refresh custom_nodes, install custom_nodes requirements, support custom_nodes with sub-modules
def clone_application(app_config:dict, venv_version:str, progress_callback) -> tuple[bool , str]:

    success = False
    message = ""
    err_message = ""
    warn_message = ""

    try:
        app_name = app_config['id']
        app_path = app_config['app_path']

        repo_url = app_config['repo_url']

        # get the current venv_version_info for the GIT params
        #branch_name = app_config['branch_name'] # setting moved into venv config
        venv_version_info = get_venv_version_info(venv_version, app_config['available_venvs'])

        branch_name = venv_version_info['branch_name']
        commit_id = venv_version_info['commit_id'] # commit_id wins over branch_name, if both set
        use_commit_id = (not (commit_id == None or commit_id == ''))
        no_checkout = False

        if use_commit_id and not (branch_name == None or branch_name == ''):
            no_checkout = True # we checkout the commit or non-default branch manually after cloning
            progress_callback('install_log', {'app_name': app_name, 'log': f"Cloning repository WARNING: commit_id '{commit_id}' and branch_name '{branch_name}' both set, 'commit_id' is used!"})
        else: # standard case: no commit_id and empty branch_name (use the default 'master' branch)
            branch_name = "master" # master branch should be checked out by default during cloning

        #clone_recursive = app_config['clone_recursive'] # setting moved into venv config
        clone_recursive = venv_version_info['clone_recursive']

        progress_callback('install_progress', {'app_name': app_name, 'percentage': 0, 'stage': 'Cloning'})

        if not os.path.exists(app_path): # install new app, otherwise refresh the app
            progress_callback('install_log', {'app_name': app_name, 'log': f"Cloning repository '{repo_url}' branch '{branch_name}' commit '{commit_id}' recursive={clone_recursive} no_checkout={no_checkout} ..."})

            repo = git.Repo.clone_from(repo_url, app_path, # first 2 params are fix, then use named params
                #branch=branch_name, # if we provide a branch here, we ONLY get this branch downloaded
                # we want ALL branches, so we can easy checkout different versions from kohya_ss late, without re-downloading
                recursive=clone_recursive, # include cloning submodules recursively (if needed as with Kohya)
                no_checkout=no_checkout, # true, if commit_id or specific (non-default) branch_name provided
                progress=lambda op_code, cur_count, max_count, message: progress_callback('install_progress', {
                    'app_name': app_name,
                    'percentage': min(int((cur_count / max_count) * 100), 100),
                    'stage': 'Cloning',
                    'processed': message
                }))

            progress_callback('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Cloning Complete'})
            progress_callback('install_log', {'app_name': app_name, 'log': 'Repository cloned successfully.'})

            # lutzapps - make sure we use Kohya with FLUX support
            if no_checkout: # no checkout during clone, so we need to checkout now manually
                if use_commit_id:
                    repo.git.checkout(commit_id)
                else:
                    repo.git.checkout(branch_name) # checkout the "sd3-flux.1" branch, but could later switch back to "master" easy
                    # the setup can be easy verified with git, here e.g. for the "kohya_ss" app:
                        # root@fe889cc68f5a:~# cd /workspace/kohya_ss
                        # root@fe889cc68f5a:/workspace/kohya_ss# git branch
                        # master
                        # * sd3-flux.1
                        # root@fe889cc68f5a:/workspace/kohya_ss# cd sd-scripts
                        # root@fe889cc68f5a:/workspace/kohya_ss/sd-scripts# git branch
                        # * (HEAD detached at b8896aa)
                        # main
                    #
                    # in the case of kohya_ss we need to fix a bug in the 'setup.sh' file,
                    # where they forgot to adapt the branch name from "master" to "sd3-flux.1"
                    # in the "#variables" section for refreshing kohya via git with 'setup.sh'

        else: # app_folder exists, refresh app
            # APP folder (mandatory) size check
            venv_path = app_config['venv_path']
            success, installed_venv_info, message = get_installed_venv_info(venv_path) # get the hidden installed_venv_info MANIFEST from the VENV

            if success:
                app_verified, message = verify_folder_size("APP", app_path, installed_venv_info, check_size=True)
                if not app_verified:
                    progress_callback('install_log', {'app_name': app_name, 'log': message})

                    return False, message
            else:
                progress_callback('install_log', {'app_name': app_name, 'log': message})

                return False, message

            # check the app_config for 'allow_refresh'
            allow_refresh = app_config['allow_refresh'] # default is that only bkohya opt-out from refresh,
            # until I test the below recursive git pull, or, in the case of 'kohya_ss' via "setup.sh"
            if not allow_refresh:
                progress_callback('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Installation Complete'})
                message = f"{app_name} is setup to not auto-refresh currently"
                progress_callback('install_log', {'app_name': app_name, 'log': message})

                return False, message
                            
            # TODO: implement app refreshes via git pull or - in the case of 'kohya_ss' - via "setup.sh"
            message = f"Refreshing repository '{repo_url}' branch '{branch_name}' commit '{commit_id}' recursive={clone_recursive} ..."
            progress_callback('install_log', {'app_name': app_name, 'log': message})

            repo = git.Repo(app_path)
            # app refresh mean a git pull (which is git fetch and git merge)
            git_status = repo.git.status()
            message = f"Initialized REPO, Git status: {git_status}"
            progress_callback('install_log', {'app_name': app_name, 'log': message})

            # check if app refresh (git pull) is really needed
            if not "Your branch is up to date" in git_status:
                # BEFORE we "git pull", we need to take back known modifications from ALL tracked files
                # If Git notices any conflicting files in the user’s workspace,
                # it aborts the task of updating the user’s workspace and only updates the user’s local Git repo.
                # this then only results in a "git fetch" and NOT updating our CWD

                # file-by-file version 'git restore <file>'
                # BKOHYA changes:
                # if app_name == 'bkohya':
                #     setup_sh_path = os.path.join(app_path, 'setup.sh')
                #     repo.index.checkout(setup_sh_path, force=True)

                # discard ANY current changes
                repo.git.reset('--hard')
                # if you need to reset to a specific branch:    
                #repo.git.reset('--hard', 'origin/master')

                # alternate command (more "GitPython like")
                # to ensure that the staging area and working tree are overwritten
                #repo.head.reset(index=True, working_tree=True)

                progress_callback('install_progress', {'app_name': app_name, 'percentage': 33, 'stage': 'Cloning', 'processed': 'reset'})

                git_status = repo.git.status()
                message = f"REPO Hard Reset, Git status: {git_status}"
                progress_callback('install_log', {'app_name': app_name, 'log': message})

                origin = repo.remotes.origin
                origin.pull() # translates to 'git pull remote origin'

                git_status = repo.git.status()
                message = f"REPO Remote Origin Pulled, Git status: {git_status}"
                progress_callback('install_log', {'app_name': app_name, 'log': message})

            ### TODO: this needs to be tested and then activated for BKOHYA
            if clone_recursive: # we need to refesh also the sub-modules of the app repo
                for submodule in repo.submodules:
                    submodule.update(init=True)
                    # same as below (if need the output from StdOut)
                    #output = repo.git.submodule('update', '--init')
                    #print(output)

                    # submodule.module() are Repo full objects:
                    # REMEMBER: git fetch + git merge = git pull
                    #sub_repo = submodule.module()
                    #sub_repo.git.checkout('devel')
                    #sub_repo.git.remote('maybeorigin').fetch()

            progress_callback('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Cloning Complete'})
            progress_callback('install_log', {'app_name': app_name, 'log': 'Repository refreshed successfully.'})

        warn_message = "" # from here on, handle smaller errors soft and only report them as warnings

        # Clone/Refresh 'ComfyUI-Manager' and other defined custom_nodes for Better ComfyUI
        if app_name == 'bcomfy':
            #venv_path = app_config['venv_path'] # need to activate VENV during installation
            #app_path = app_config['app_path'] # already defined

            # install all defined custom nodes
            custom_nodes_path = os.path.join(app_path, 'custom_nodes')
            os.makedirs(f"{custom_nodes_path}/", exist_ok=True) # append a trailing slash to be sure last dir is created

            custom_nodes_errors = 0
            custom_nodes_error_details = ""

            progress_callback('install_progress', {'app_name': app_name, 'percentage': 0, 'stage': 'Cloning', 'processed': 'custom nodes'})
            progress_callback('install_log', {'app_name': app_name, 'log': 'Installing/cloning custom nodes ...'})

            # calculate the progress step multiplier
            custom_nodes_count = len(app_config['custom_nodes'])
            custom_node_number = -1 # runs from 0 to (custom_nodes_count - 1)
            node_delta = 100 / custom_nodes_count

            for custom_node in app_config['custom_nodes']:
                custom_node_number += 1 # 0 to custom_nodes_count - 1

                err_message = "" # clear last error from last node

                node_venv_version = custom_node['venv_version']
                if not (node_venv_version == '*' or node_venv_version == venv_version):
                    continue # skip this custom_node installation for this venv_version

                name = custom_node['name']
                path = custom_node['path']
                repo_url = custom_node['repo_url']
                
                clone_recursive = custom_node['clone_recursive']
                # some custom_nodes need a recursive clone, e.g. 'ComfyUI UltimateSDUpscale (ssitu)',
                # but they NOT have a requirements.txt file to install requirements
                install_requirements_txt = custom_node['install_requirements_txt']

                custom_node_path = os.path.join(custom_nodes_path, path)
                is_refresh = os.path.exists(custom_node_path)
                need_refresh = not is_refresh # new app setup need refresh (aka 'install-requirements')
                # in refresh mode , git status further sets need_refresh
                
                try:
                    if not is_refresh: # install new custom nodes
                        progress_callback('install_log', {'app_name': app_name, 'log': f"- - - - - -"}) # new-line
                        progress_callback('install_log', {'app_name': app_name, 'log': f"Cloning custom_node '{name}' ..."})
                        
                        #git.Repo.clone_from(repo_url, custom_node_path)
                        repo = git.Repo.clone_from(repo_url, custom_node_path, 
                            recursive=clone_recursive, # some custom_nodes need a recursive clone, e.g. 'ComfyUI UltimateSDUpscale (ssitu)'
                            progress=lambda op_code, cur_count, max_count, message: progress_callback('install_progress', {
                                'app_name': app_name,
                                'percentage': min(int((custom_node_number * node_delta) + (cur_count / max_count) * node_delta), 100),
                                'stage': 'Cloning',
                                'processed': message
                            }))
                        
                        progress_callback('install_log', {'app_name': app_name, 'log': f"custom_node '{name}' was cloned successfully."})

                    else: # existing custom_node folder, so we do a refresh
                        progress_callback('install_log', {'app_name': app_name, 'log': f"- - - - - -"}) # new-line
                        progress_callback('install_log', {'app_name': app_name, 'log': f"Refreshing/pull custom_node '{name}' ..."})

                        repo = git.Repo(custom_node_path) # repo_url (custom_node)

                        git_status = repo.git.status()
                        message = f"Initialized REPO, Git status: {git_status}"
                        progress_callback('install_log', {'app_name': app_name, 'log': message})
                        #print(message)

                        # check if refresh is needed
                        need_refresh = (not "Your branch is up to date" in git_status)

                        if need_refresh:
                            # discard any current local changes
                            repo.git.reset('--hard')

                            git_status = repo.git.status()
                            message = f"REPO Hard Reset, Git status: {git_status}"
                            progress_callback('install_log', {'app_name': app_name, 'log': message})
                            #print(message)

                            origin = repo.remotes.origin
                            origin.pull()

                            git_status = repo.git.status()
                            message = f"REPO Remote Origin Pulled, Git status: {git_status}"
                            progress_callback('install_log', {'app_name': app_name, 'log': message})
                            #print(message)

                            if clone_recursive: # we need to refesh also the sub-modules of the custom_node repo
                                for submodule in repo.submodules:
                                    submodule.update(init=True)

                            progress_callback('install_log', {'app_name': app_name, 'log': f"custom_node '{name}' was refreshed/pulled successfully."})

                except Exception as e:
                    err_message = str(e)
                    custom_nodes_errors += 1
                    custom_nodes_error_details += f"\nCloning/Refreshing custom_node '{name}'\n:{err_message}\n"

                # install the requirements for this custom node
                # (this needs to be theorectically also be done for Refreshes, if a new Python module is used by the custom_node)
                
                # check if we need to install, and if this custom node has a known requirement setting and 'requirements.txt' file exists
                if not need_refresh or not (install_requirements_txt and os.path.exists(os.path.join(custom_node_path, "requirements.txt"))):
                    progress_callback('install_log', {'app_name': app_name, 'log': f"skipping requirements installation for custom_node '{name}'"})
                    continue # skip this node for requirements installation, as it opts out or no default 'requirements.txt' file exists
                
                success = False
                message = ""
                err_message = ""

                try:
                    cmd_key = 'install-requirements'
                    message = f"Installing/refreshing requirements for custom_node '{name}' ..."
                    progress_callback('install_log', {'app_name': app_name, 'log': f"- - - - - -"}) # new-line
                    progress_callback('install_log', {'app_name': app_name, 'log': message})

                    success, message = run_bash_cmd(app_config, cwd=custom_node_path, cmd_key=cmd_key, progress_callback=progress_callback)

                    if success: # message == ""
                        message = f"Requirements for custom_node '{name}' were successfully installed/refreshed."
                    else:
                        err_message = message
                        custom_nodes_errors += 1
                        custom_nodes_error_details += f"\nPIP install requirements error for custom_node '{name}'\n:{err_message}\n"

                    progress_callback('install_log', {'app_name': app_name, 'log': message})

                except Exception as e:
                    err_message = str(e)
                    custom_nodes_errors += 1
                    custom_nodes_error_details += f"\nException in install requirements for custom_node '{name}'\n:{err_message}\n"

                # after each custom_node, update the progress bar
                progress_callback('install_progress', {'app_name': app_name, 'percentage': ((custom_node_number + 1) * node_delta), 'stage': 'Cloning', 'processed': '{name}'})

            # after all custom nodes
            if custom_nodes_errors > 0:
                #print(custom_nodes_error_details)
                progress_callback('install_log', {'app_name': app_name, 'log': f"- - - - - -"}) # new-line
                progress_callback('install_log', {'app_name': app_name, 'log': custom_nodes_error_details})
                warn_message += f"\n{custom_nodes_error_details}" # pass summary down as warning

            ### always run the cmd to install/update comfy CLI
            cmd_key = 'install-comfy-CLI'
            message = f"Installing/Refreshing Comfy CLI: cmd_key='{cmd_key}' ..."
            progress_callback('install_log', {'app_name': app_name, 'log': f"- - - - - -"}) # new-line
            progress_callback('install_log', {'app_name': app_name, 'log': message})

            success, message = run_bash_cmd(app_config, cwd=app_path, cmd_key=cmd_key, progress_callback=progress_callback)

            if not success:
                warn_message += f"\ncmd '{cmd_key}' error: {message}"
            else: # message == ""
                message = f"cmd_key '{cmd_key}' did run successfully."

            progress_callback('install_log', {'app_name': app_name, 'log': message})

            ### always clean-up (pip install caches and python runtime caches)
            cmd_key = 'pip-clean-up'
            message = f"Cleaning up: cmd_key='{cmd_key}' ..."
            progress_callback('install_log', {'app_name': app_name, 'log': f"- - - - - -"}) # new-line
            progress_callback('install_log', {'app_name': app_name, 'log': message})

            success, message = run_bash_cmd(app_config, cwd=app_path, cmd_key=cmd_key, progress_callback=progress_callback)

            if not success:
                warn_message += f"\ncmd '{cmd_key}' error: {message}"
            else: # message == ""
                message = f"cmd_key '{cmd_key}' did run successfully."

            progress_callback('install_log', {'app_name': app_name, 'log': message})

            # summary after all custom_nodes
            progress_callback('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Cloning Complete'})
            message = f"There were {custom_nodes_errors} error(s) during installing/refreshing custom nodes"
            progress_callback('install_log', {'app_name': app_name, 'log': f"- - - - - -"}) # new-line
            progress_callback('install_log', {'app_name': app_name, 'log': message})


    except git.exc.GitCommandError as e:
        progress_callback('install_log', {'app_name': app_name, 'log': f'GIT Error cloning/refreshing repository: {str(e)}'})
        return False, f"Error cloning repository: {str(e)}"
    except Exception as e:
        progress_callback('install_log', {'app_name': app_name, 'log': f'Exception cloning/refreshing repository: {str(e)}'})
        return False, f"Error cloning repository: {str(e)}"

    if app_name == 'bkohya': # special handling after Setup/Refresh
        success, message = update_kohya_setup_sh(app_path) # patch the 'setup.sh' file for flux branch_name
        if not success: # patch ws not applied, can be fixed manually
            warn_message += f"\nkoyha patch for 'setup.sh' was not applied: {message}"
            #print(warn_message) # shows, if the patch was needed, and applied successfully

        # create a folder link for kohya_ss local "venv"
        success, message = ensure_kohya_local_venv_is_symlinked()
        if not success: # symlink not created, but still success=True and only a warning, can be fixed manually
            warn_message += f"\nkohya symlink creation to the local venv returned following problem: {message}"
    
    if warn_message == "": 
        message = f"'{app_name}' was installed/cloned/refreshed and patched successfully"
    else:
        message = f"'{app_name}' was installed/cloned/refreshed successfully, but following issues occured:\n{warn_message}"

    return True, message

def run_bash_cmd(app_config:dict, cwd:str, cmd_key:str, progress_callback=None) -> tuple[bool, str]:
    success = False
    message = ""

    try:
        app_name = app_config['id']
        app_path = app_config['app_path']
        venv_path = app_config['venv_path']

        bash_command = app_config['bash_cmds'][cmd_key] # get the bash_cmd value from app_config
        # resolve MAKROS in cmdline
        # Use regex to search & replace cmdline vars (currently only '{app_path}' MAKRO is supported)
        bash_command = re.sub(r'{app_path}', app_path, bash_command)
        
        # Activate the virtual environment and run the commands
        activate_venv = f"source {venv_path}/bin/activate"
        change_dir_command = f"cd {cwd}"
        
        full_command_line = f"{activate_venv} && {change_dir_command} && {bash_command}"
        
        # TODO: rewrite this without shell
        #process = subprocess.run(["pip", "install", "-r", "requirements.txt"], cwd=custom_node_path)
        # need also to activate the VENV before running PIP INSTALL
        with subprocess.Popen(full_command_line, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, executable='/bin/bash') as bash_process:
            # blocking wait
            #output, _ = bash_process.communicate()
            #message = output.decode('utf-8') # decode the byte-coded result
            #print(message)

            # stream output (line-by-line)
            for line in iter(bash_process.stdout.readline, b""):
                line_message = line.decode('utf-8').rstrip()

                if not progress_callback == None:
                    progress_callback('install_log', {'app_name': app_name, 'log': line_message})
                else:
                    print(message)

        bash_process.wait() # let the process finish
        rc = bash_process.returncode # and get the return code

        success = True
        message = ""

        if rc != 0 and cmd_key != 'run-tensorboard': # return a 'killed' tensorboard process as success, so the Stop-Button works correct in the UI (otherwise it needs to be clicked twice)
            success = False
            message = f"Bash cmd '{cmd_key}' failed: {bash_process.stderr.read() if bash_process.stderr else 'Unknown error'}"

    except Exception as e:
        message = str(e)

    return success, message

def update_kohya_setup_sh(app_path:str) -> tuple[bool, str]:
    try:
        # patch 'setup.sh' within the kohya_ss main folder for BRANCH="sd3-flux.1"
        setup_sh_path = os.path.join(app_path, 'setup.sh')
        if not os.path.exists(setup_sh_path):
            return False, f"file '{setup_sh_path}' was not found"

        with open(setup_sh_path, 'r') as file:
            content = file.read()

        # Use regex to search & replace wrong branch variable in the file
        patched_content = re.sub(r'BRANCH="master"', 'BRANCH="sd3-flux.1"', content)

        if patched_content == content:
            message = f"'{setup_sh_path}' already fine, patch not needed."
        else:
            with open(setup_sh_path, 'w') as file:
                file.write(patched_content)

            message = f"'{setup_sh_path}' needed patch, successfully patched."

        return True, message
    
    except Exception as e:
        return False, str(e)


def fix_custom_nodes(app_name:str, app_configs:dict) ->tuple[bool, str]:
    if app_name != 'bcomfy':
        return False, "This operation is only available for Better ComfyUI."
    
    app_config = app_configs[app_name]
    
    #venv_path = app_configs['bcomfy']['venv_path']
    app_path = app_configs['bcomfy']['app_path']

    try:
        cmd_key = 'fix-custom_nodes'
        message = f"Fix custom nodes: cmd_key='{cmd_key}'"
        #progress_callback('install_log', {'app_name': app_name, 'log': message})
        print(message)

        success, message = run_bash_cmd(app_config, cwd=app_path, cmd_key=cmd_key, progress_callback=None)

        if success:
            return True, f"Custom nodes fixed successfully. Output: {message}" # message == ""
        else:
            print(message) # error_message
            return False, f"Error fixing custom nodes. Output: {message}"
        
    except Exception as e:
        return False, f"Error fixing custom nodes: {str(e)}"

def get_available_venvs(app_name:str) -> tuple[bool, dict]:
    app_config = app_configs.get(app_name)

    if not app_config:
        return False, {}

    try:
        success = True
        
        # get the 'available_venvs' list from app_config
        available_venvs = app_config['available_venvs']

        # get the VENV info
        # can be overwritten with 'VENV_VERSION_<app_id>' ENV var or via DEBUG_SETTINGS['venv_version']
        # user can e.g. set the VENV_VERSION_BA1111='latest', or same for VENV_VERSION_BFORGE, VENV_VERSION_BCOMFY, VENV_VERSION_BKOHYA
        # default is to use the 'latest' VENV
        env_venv_version_app = f'VENV_VERSION_{app_name.upper()}'
        selected_venv_version = os.environ.get(env_venv_version_app, '') # default setting is '' (empty)
        if not selected_venv_version == '': # user-defined VENV selected via app-specific ENV var
            print(f"ENV var '{env_venv_version_app}={selected_venv_version}' overwrite for VENV environment detected")        

        debug_selected_venv_version = DEBUG_SETTINGS['select_venv_version'] # check for master overwrite
        if not (debug_selected_venv_version == None or debug_selected_venv_version == ''): # overwrite of 'selected_venv_version'
            selected_venv_version = debug_selected_venv_version # 'latest' or 'official' (or 'experimental')
            print(f"DEBUG '{selected_venv_version}' overwrite for VENV environment detected")        

        if not (selected_venv_version == None or selected_venv_version == ''): # if ENV var or DEBUG_SETTINGS selection is already found
            # try to find the selected venv_version in the 'available_venvs' of the app
            venv_version_info = get_venv_version_info(selected_venv_version, available_venvs)
            if not venv_version_info == {}: # user selection was a valid VENV, which was found in available_venvs
                available_venvs = [venv_version_info] # only return the ONE selected venv (as single list-item), so the venv-picker dialog can be by-passed
            #else: # let the user select from all available_venvs


    except Exception as e:
        success = False
        available_venvs = {
            'message: ' + str(e)
        }

    return success, available_venvs # ONE or more venv_version(s)

# lutzapps - Replace the existing install_app function with this updated version
def install_app(app_name:str, venv_version:str, progress_callback) -> tuple[bool, str]:
    if not app_name in app_configs:
        return False, f"Unknown app: {app_name}"

    print(f"download_and_unpack_venv() STARTING for '{app_name}'")

    import time
    start_time = time.time()
          
    success, message = download_and_unpack_venv(app_name, venv_version, progress_callback)

    total_duration = f"{datetime.timedelta(seconds=int(time.time() - start_time))}"

    write_debug_setting('total_duration', total_duration)

    print(f"download_and_unpack_venv() did run {total_duration} for app '{app_name}'")
    return success, message    
