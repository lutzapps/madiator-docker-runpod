from gevent import monkey
monkey.patch_all()

import os
import threading
import time
from flask import Flask, render_template, jsonify, request
from flask_sock import Sock
import json
import signal
import shutil
import subprocess
import traceback

from utils.ssh_utils import setup_ssh, save_ssh_password, get_ssh_password, check_ssh_config, SSH_CONFIG_FILE
from utils.filebrowser_utils import configure_filebrowser, start_filebrowser, stop_filebrowser, get_filebrowser_status, FILEBROWSER_PORT
from utils.app_utils import (
    run_app, update_process_status, check_app_directories, get_app_status,
    force_kill_process_by_name, update_webui_user_sh, save_install_status,
    get_install_status, download_and_unpack_venv, fix_custom_nodes, is_process_running, install_app, # update_model_symlinks
    get_bkohya_launch_url # lutzapps - support dynamic generated gradio url
)

# lutzapps - CHANGE #1
LOCAL_DEBUG = os.environ.get('LOCAL_DEBUG', 'False') # support local browsing for development/debugging

# use the new "utils.shared_models" module for app model sharing
from utils.shared_models import (
    update_model_symlinks, # main WORKER function (file/folder symlinks, Fix/remove broken symlinks, pull back local app models into shared)
    SHARED_MODELS_DIR, SHARED_MODEL_FOLDERS, SHARED_MODEL_FOLDERS_FILE, ensure_shared_models_folders,
    APP_INSTALL_DIRS, APP_INSTALL_DIRS_FILE, init_app_install_dirs, # APP_INSTALL_DIRS dict/file/function
    MAP_APPS, sync_with_app_configs_install_dirs, # internal MAP_APPS dict and sync function
    SHARED_MODEL_APP_MAP, SHARED_MODEL_APP_MAP_FILE, init_shared_model_app_map # SHARED_MODEL_APP_MAP dict/file/function
)
# the "update_model_symlinks()" function replaces the app.py function with the same same
# and redirects to same function name "update_model_symlinks()" in the new "utils.shared_models" module
#
# this function does ALL the link management, including deleting "stale" symlinks,
# so the "recreate_symlinks()" function will be also re-routed to the
# "utils.shared_models.update_model_symlinks()" function (see CHANGE #3a and CHANGE #3b)

# the "ensure_shared_models_folders()" function will be called from app.py::create_shared_folders(),
# and replaces this function (see CHANGE #3)

# the "init_app_install_dirs() function initializes the
#   global module 'APP_INSTALL_DIRS' dict: { 'app_name': 'app_installdir' }
# which does a default mapping from app code or (if exists) from external JSON 'APP_INSTALL_DIRS_FILE' file
# NOTE: this APP_INSTALL_DIRS dict is temporary synced with the 'app_configs' dict (see next)

# the "sync_with_app_configs_install_dirs() function syncs the 'APP_INSTALL_DIRS' dict's 'app_installdir' entries
# from the 'app_configs' dict's 'app_path' entries and uses the MAP_APPS dict for this task
# NOTE: this syncing is a temporary solution, and needs to be better integrated later

# the "init_shared_model_app_map()" function initializes the
#   global module 'SHARED_MODEL_APP_MAP' dict: 'model_type' -> 'app_name:app_model_dir' (relative path)
# which does a default mapping from app code or (if exists) from external JSON 'SHARED_MODEL_APP_MAP_FILE' file


from utils.websocket_utils import send_websocket_message, active_websockets
from utils.app_configs import get_app_configs, add_app_config, remove_app_config, app_configs
from utils.model_utils import download_model, check_civitai_url, check_huggingface_url, format_size #, SHARED_MODELS_DIR # lutzapps - SHARED_MODELS_DIR is owned by shared_models module now

app = Flask(__name__)
sock = Sock(app)

RUNPOD_POD_ID = os.environ.get('RUNPOD_POD_ID', 'localhost')

running_processes = {}

app_configs = get_app_configs()

#S3_BASE_URL = "https://better.s3.madiator.com/" # unused now

SETTINGS_FILE = '/workspace/.app_settings.json'

CIVITAI_TOKEN_FILE = '/workspace/.civitai_token'
HF_TOKEN_FILE = '/workspace/.hf_token' # lutzapps - added support for HF_TOKEN_FILE


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {'auto_generate_ssh_password': False}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

def check_running_processes():
    while True:
        for app_name in list(running_processes.keys()):
            update_process_status(app_name, running_processes)
            current_status = get_app_status(app_name, running_processes)
            send_websocket_message('status_update', {app_name: current_status})
        time.sleep(5)

@app.route('/')
def index():
    settings = load_settings()
    
    # Determine the current SSH authentication method
    with open(SSH_CONFIG_FILE, 'r') as f:
        ssh_config = f.read()
    current_auth_method = 'key' if 'PasswordAuthentication no' in ssh_config else 'password'

    # Get the current SSH password if it exists
    ssh_password = get_ssh_password()
    ssh_password_status = 'set' if ssh_password else 'not_set'

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
            'is_bcomfy': app_name == 'bcomfy'
        }

    filebrowser_status = get_filebrowser_status()
    return render_template('index.html', 
                         apps=app_configs, 
                         app_status=app_status, 
                         pod_id=RUNPOD_POD_ID, 
                         RUNPOD_PUBLIC_IP=os.environ.get('RUNPOD_PUBLIC_IP'),
                         RUNPOD_TCP_PORT_22=os.environ.get('RUNPOD_TCP_PORT_22'),
                         enable_unsecure_localhost=os.environ.get('LOCAL_DEBUG'),
                         settings=settings,
                         current_auth_method=current_auth_method,
                         ssh_password=ssh_password,
                         ssh_password_status=ssh_password_status,
                         filebrowser_status=filebrowser_status)

@app.route('/start/<app_name>')
def start_app(app_name):
    dirs_ok, message = check_app_directories(app_name, app_configs)
    if not dirs_ok:
        return jsonify({'status': 'error', 'message': message})
    
    if app_name in app_configs and get_app_status(app_name, running_processes) == 'stopped':
        # Update webui-user.sh for Forge and A1111
        if app_name in ['bforge', 'ba1111']:
            update_webui_user_sh(app_name, app_configs)

        command = app_configs[app_name]['command']
        threading.Thread(target=run_app, args=(app_name, command, running_processes)).start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})

@app.route('/stop/<app_name>')
def stop_app(app_name):
    if app_name in running_processes and get_app_status(app_name, running_processes) == 'running':
        try:
            pgid = os.getpgid(running_processes[app_name]['pid'])
            os.killpg(pgid, signal.SIGTERM)
            
            for _ in range(10):
                if not is_process_running(running_processes[app_name]['pid']):
                    break
                time.sleep(1)
            
            if is_process_running(running_processes[app_name]['pid']):
                os.killpg(pgid, signal.SIGKILL)
            
            running_processes[app_name]['status'] = 'stopped'
            return jsonify({'status': 'stopped'})
        except ProcessLookupError:
            running_processes[app_name]['status'] = 'stopped'
            return jsonify({'status': 'already_stopped'})
    return jsonify({'status': 'not_running'})

@app.route('/status')
def get_status():
    return jsonify({app_name: get_app_status(app_name, running_processes) for app_name in app_configs})

@app.route('/logs/<app_name>')
def get_logs(app_name):
    if app_name in running_processes:
        return jsonify({'logs': running_processes[app_name]['log'][-100:]})
    return jsonify({'logs': []})

# lutzapps - support bkohya gradio url
@app.route('/get_bkohya_launch_url', methods=['GET'])
def get_bkohya_launch_url_route():
    command =  app_configs['bkohya']['command']
    is_gradio = ("--share" in command.lower()) # gradio share mode
    if is_gradio:
        mode = 'gradio'
    else:
        mode = 'local'

    launch_url = get_bkohya_launch_url() # get this from the app_utils global BKOHYA_GRADIO_URL, which is polled from the kohya log
    return jsonify({ 'mode': mode, 'url': launch_url }) # used from the index.html:OpenApp() button click function

@app.route('/kill_all', methods=['POST'])
def kill_all():
    try:
        for app_key in app_configs:
            if get_app_status(app_key, running_processes) == 'running':
                stop_app(app_key)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/force_kill/<app_name>', methods=['POST'])
def force_kill_app(app_name):
    try:
        success, message = force_kill_process_by_name(app_name, app_configs)
        if success:
            return jsonify({'status': 'killed', 'message': message})
        else:
            return jsonify({'status': 'error', 'message': message})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

from gevent.lock import RLock
websocket_lock = RLock()

@sock.route('/ws')
def websocket(ws):
    with websocket_lock:
        active_websockets.add(ws)
    try:
        while ws.connected:  # Check connection status
            try:
                message = ws.receive(timeout=70)  # Add timeout slightly higher than heartbeat
                if message:
                    data = json.loads(message)
                    if data['type'] == 'heartbeat':
                        ws.send(json.dumps({'type': 'heartbeat'}))
                    else:
                        # Handle other message types
                        pass
            except Exception as e:
                if "timed out" in str(e).lower():
                    # Handle timeout gracefully
                    continue
                print(f"Error handling websocket message: {str(e)}")
                if not ws.connected:
                    break
                continue
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        with websocket_lock:
            try:
                active_websockets.remove(ws)
            except KeyError:
                pass

def send_heartbeat():
    while True:
        try:
            time.sleep(60)  # Fixed 60 second interval
            with websocket_lock:
                for ws in list(active_websockets):  # Create a copy of the set
                    try:
                        if ws.connected:
                            ws.send(json.dumps({'type': 'heartbeat', 'data': {}}))
                    except Exception as e:
                        print(f"Error sending heartbeat: {str(e)}")
        except Exception as e:
            print(f"Error in heartbeat thread: {str(e)}")

# Start heartbeat thread
threading.Thread(target=send_heartbeat, daemon=True).start()

@app.route('/install/<app_name>', methods=['POST'])
def install_app_route(app_name):
    try:
        def progress_callback(message_type, message_data):
            try:
                send_websocket_message(message_type, message_data)
            except Exception as e:
                print(f"Error sending progress update: {str(e)}")
                # Continue even if websocket fails
                pass

        success, message = install_app(app_name, app_configs, progress_callback)
        if success:
            return jsonify({'status': 'success', 'message': message})
        else:
            return jsonify({'status': 'error', 'message': message})
    except Exception as e:
        error_message = f"Installation error for {app_name}: {str(e)}\n{traceback.format_exc()}"
        app.logger.error(error_message)
        return jsonify({'status': 'error', 'message': error_message}), 500

@app.route('/fix_custom_nodes/<app_name>', methods=['POST'])
def fix_custom_nodes_route(app_name):
    success, message = fix_custom_nodes(app_name)
    if success:
        return jsonify({'status': 'success', 'message': message})
    else:
        return jsonify({'status': 'error', 'message': message})

@app.route('/set_ssh_password', methods=['POST'])
def set_ssh_password():
    try:
        data = request.json
        new_password = data.get('password')
        
        if not new_password:
            return jsonify({'status': 'error', 'message': 'No password provided'})
        
        print("Attempting to set new password...")
        
        # Use chpasswd to set the password
        process = subprocess.Popen(['chpasswd'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, error = process.communicate(input=f"root:{new_password}\n")
        
        if process.returncode != 0:
            raise Exception(f"Failed to set password: {error}")
        
        # Save the new password
        save_ssh_password(new_password)
        
        # Configure SSH to allow root login with password
        print("Configuring SSH to allow root login with a password...")
        subprocess.run(["sed", "-i", 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/', "/etc/ssh/sshd_config"], check=True)
        subprocess.run(["sed", "-i", 's/#PasswordAuthentication no/PasswordAuthentication yes/', "/etc/ssh/sshd_config"], check=True)
        
        # Restart SSH service to apply changes
        print("Restarting SSH service...")
        subprocess.run(['service', 'ssh', 'restart'], check=True)
        print("SSH service restarted successfully.")
        
        print("SSH Configuration Updated and Password Set.")
        
        return jsonify({'status': 'success', 'message': 'SSH password set successfully. Note: Key-based authentication is more secure.'})
    except Exception as e:
        error_message = f"Error in set_ssh_password: {str(e)}\n{traceback.format_exc()}"
        print(error_message)
        return jsonify({'status': 'error', 'message': error_message})

@app.route('/start_filebrowser')
def start_filebrowser_route():
    if start_filebrowser():
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})

@app.route('/stop_filebrowser')
def stop_filebrowser_route():
    if stop_filebrowser():
        return jsonify({'status': 'stopped'})
    return jsonify({'status': 'already_stopped'})

@app.route('/filebrowser_status')
def filebrowser_status_route():
    try:
        status = get_filebrowser_status()
        return jsonify({'status': status if status else 'unknown'})
    except Exception as e:
        app.logger.error(f"Error getting filebrowser status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/add_app_config', methods=['POST'])
def add_new_app_config():
    data = request.json
    app_name = data.get('app_name')
    config = data.get('config')
    if app_name and config:
        add_app_config(app_name, config)
        return jsonify({'status': 'success', 'message': f'App {app_name} added successfully'})
    return jsonify({'status': 'error', 'message': 'Invalid data provided'})

@app.route('/remove_app_config/<app_name>', methods=['POST'])
def remove_existing_app_config(app_name):
    if app_name in app_configs:
        remove_app_config(app_name)
        return jsonify({'status': 'success', 'message': f'App {app_name} removed successfully'})
    return jsonify({'status': 'error', 'message': f'App {app_name} not found'})

# modified function
def setup_shared_models():
    # lutzapps - CHANGE #4 - use the new "shared_models" module for app model sharing
    jsonResult = update_model_symlinks()

    return SHARED_MODELS_DIR # shared_models_dir is now owned and managed by the "shared_models" utils module

def update_symlinks_periodically():
    while True: 
        update_model_symlinks()
        time.sleep(300)  # Check every 5 minutes

def start_symlink_update_thread():
    thread = threading.Thread(target=update_symlinks_periodically, daemon=True)
    thread.start()

# modified function
@app.route('/recreate_symlinks', methods=['POST'])
def recreate_symlinks_route():
    # lutzapps - CHANGE #7 - use the new "shared_models" module for app model sharing
    jsonResult = update_model_symlinks()

    return jsonResult

# modified function
@app.route('/create_shared_folders', methods=['POST'])
def create_shared_folders():
    # lutzapps - CHANGE #8 - use the new "shared_models" module for app model sharing
    jsonResult = ensure_shared_models_folders()
    return jsonResult

def save_civitai_token(token):
    with open(CIVITAI_TOKEN_FILE, 'w') as f:
        json.dump({'token': token}, f)

# lutzapps - added function - 'HF_TOKEN' ENV var
def load_huggingface_token():
    # look FIRST for Huggingface token passed in as 'HF_TOKEN' ENV var
    HF_TOKEN = os.environ.get('HF_TOKEN', '')
    
    if not HF_TOKEN == "":
        print("'HF_TOKEN' ENV var found")
        ## send the found token to the WebUI "Models Downloader" 'hfToken' Password field to use
        # send_websocket_message('extend_ui_helper', {
        #     'cmd': 'hfToken', # 'hfToken' must match the DOM Id of the WebUI Password field in "index.html"
        #     'message': "Put the HF_TOKEN in the WebUI Password field 'hfToken'"
        # } )

        return HF_TOKEN
    
    # only if the 'HF_API_TOKEN' ENV var was not found, then handle it via local hidden HF_TOKEN_FILE
    try:
        if os.path.exists(HF_TOKEN_FILE):
            with open(HF_TOKEN_FILE, 'r') as f:
                data = json.load(f)

                return data.get('token')
    except:
        return None

    return None

# lutzapps - modified function - support 'CIVITAI_API_TOKEN' ENV var
def load_civitai_token():
    # look FIRST for CivitAI token passed in as 'CIVITAI_API_TOKEN' ENV var
    CIVITAI_API_TOKEN = os.environ.get('CIVITAI_API_TOKEN', '')
    
    if not CIVITAI_API_TOKEN == "":
        print("'CIVITAI_API_TOKEN' ENV var found")
        ## send the found token to the WebUI "Models Downloader" 'hfToken' Password field to use
        # send_websocket_message('extend_ui_helper', {
        #     'cmd': 'civitaiToken', # 'civitaiToken' must match the DOM Id of the WebUI Password field in "index.html"
        #     'message': 'Put the CIVITAI_API_TOKEN in the WebUI Password field "civitaiToken"'
        # } )

        return CIVITAI_API_TOKEN
    
    # only if the 'CIVITAI_API_TOKEN' ENV var is not found, then handle it via local hidden CIVITAI_TOKEN_FILE
    try:
        if os.path.exists(CIVITAI_TOKEN_FILE):
            with open(CIVITAI_TOKEN_FILE, 'r') as f:
                data = json.load(f)

                return data.get('token')
    except:
        return None
        
    return None

@app.route('/save_civitai_token', methods=['POST'])
def save_civitai_token_route():
    token = request.json.get('token')
    if token:
        save_civitai_token(token)
        return jsonify({'status': 'success', 'message': 'Civitai token saved successfully.'})
    return jsonify({'status': 'error', 'message': 'No token provided.'}), 400

@app.route('/get_civitai_token', methods=['GET'])
def get_civitai_token_route():
    token = load_civitai_token()
    return jsonify({'token': token})

# lutzapps - add support for passed in "HF_TOKEN" ENV var
@app.route('/get_huggingface_token', methods=['GET'])
def get_hugginface_token_route():
    token = load_huggingface_token()
    return jsonify({'token': token})

# lutzapps - CHANGE #9 - return model_types to populate the Download manager Select Option
# new function to support the "Model Downloader" with the 'SHARED_MODEL_FOLDERS' dictionary
@app.route('/get_model_types', methods=['GET'])
def get_model_types_route():
    model_types_dict = {}
    
    # check if the SHARED_MODELS_DIR exists at the "/workspace" location!
    # that only happens AFTER the the user clicked the "Create Shared Folders" button
    # on the "Settings" Tab of the app's WebUI!
    # to reload existing SHARED_MODEL_FOLDERS into the select options dropdown list,
    # we send a WebSockets message to "index.html"
    
    if not os.path.exists(SHARED_MODELS_DIR):
        # return an empty model_types_dict, so the "Download Manager" does NOT get
        # the already in-memory SHARED_MODEL_FOLDERS code-generated default dict
        # BEFORE the workspace folders in SHARED_MODELS_DIR exists
        return model_types_dict
    
    i = 0
    for model_type, model_type_description in SHARED_MODEL_FOLDERS.items():
        model_types_dict[i] = {
            'modelfolder': model_type,
            'desc': model_type_description
        }

        i += 1
    
    return model_types_dict

@app.route('/download_model', methods=['POST'])
def download_model_route():
    try:
        data = request.json
        url = data.get('url')
        model_name = data.get('model_name')
        model_type = data.get('model_type')
        civitai_token = data.get('civitai_token')
        hf_token = data.get('hf_token')
        version_id = data.get('version_id')
        file_index = data.get('file_index')

        # If no token provided in request, try to read from file
        if not civitai_token:
            try:
                if os.path.exists('/workspace/.civitai_token'):
                    with open('/workspace/.civitai_token', 'r') as f:
                        token_data = json.load(f)
                        civitai_token = token_data.get('token')
            except Exception as e:
                app.logger.error(f"Error reading token file: {str(e)}")

        is_civitai, _, _, _ = check_civitai_url(url)
        is_huggingface, _, _, _, _ = check_huggingface_url(url)

        if not (is_civitai or is_huggingface):
            return jsonify({'status': 'error', 'message': 'Unsupported URL. Please use Civitai or Hugging Face URLs.'}), 400

        if is_civitai and not civitai_token:
            return jsonify({'status': 'error', 'message': 'Civitai token is required for downloading from Civitai.'}), 400

        try:
            success, message = download_model(url, model_name, model_type, civitai_token, hf_token, version_id, file_index)
            if success:
                if isinstance(message, dict) and 'choice_required' in message:
                    return jsonify({'status': 'choice_required', 'data': message['choice_required']})
                return jsonify({'status': 'success', 'message': message})
            else:
                return jsonify({'status': 'error', 'message': message}), 400
        except Exception as e:
            error_message = f"Model download error: {str(e)}\n{traceback.format_exc()}"
            app.logger.error(error_message)
            return jsonify({'status': 'error', 'message': error_message}), 500

    except Exception as e:
        error_message = f"Error processing request: {str(e)}\n{traceback.format_exc()}"
        app.logger.error(error_message)
        return jsonify({'status': 'error', 'message': error_message}), 400

@app.route('/get_model_folders')
def get_model_folders():
    folders = {}
    
    # lutzapps - replace the hard-coded model types
    for folder, model_type_description in SHARED_MODEL_FOLDERS.items():
    #for folder in ['Stable-diffusion', 'VAE', 'Lora', 'ESRGAN']:
        folder_path = os.path.join(SHARED_MODELS_DIR, folder)
        if os.path.exists(folder_path):
            total_size = 0
            file_count = 0
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
                    file_count += 1
            folders[folder] = {
                'size': format_size(total_size),
                'file_count': file_count
            }
    return jsonify(folders)

@app.route('/update_symlinks', methods=['POST'])
def update_symlinks_route():
    try:
        update_model_symlinks()
        return jsonify({'status': 'success', 'message': 'Symlinks updated successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    shared_models_path = setup_shared_models()
    print(f"Shared models directory: {shared_models_path}")
    
    if setup_ssh():
        print("SSH setup completed successfully.")
    else:
        print("Failed to set up SSH. Please check the logs.")
    
    print("Configuring File Browser...")
    if configure_filebrowser():
        print("File Browser configuration completed successfully.")
        print("Attempting to start File Browser...")
        if start_filebrowser():
            print("File Browser started successfully.")
        else:
            print("Failed to start File Browser. Please check the logs.")
    else:
        print("Failed to configure File Browser. Please check the logs.")
    
    threading.Thread(target=check_running_processes, daemon=True).start()
    
    # Start the thread to periodically update model symlinks
    start_symlink_update_thread()
    
    app.run(debug=True, host='0.0.0.0', port=7223)