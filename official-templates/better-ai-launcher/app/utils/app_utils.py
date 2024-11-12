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
from utils.app_configs import (app_configs, DEBUG_SETTINGS, pretty_dict, init_app_configs, init_debug_settings, write_debug_setting, ensure_kohya_local_venv_is_symlinked)
from utils.model_utils import (get_sha256_hash_from_file)

INSTALL_STATUS_FILE = '/tmp/install_status.json'

# lutzapps - support for bkohya gradio url
BKOHYA_LAUNCH_URL = "" # will be captured during run_app('bkohya', ...) from bkohya log
# e.g. https://85f6f17d6d725c6cde.gradio.live

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

def check_app_directories(app_name, app_configs):
    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."
    
    venv_path = app_config['venv_path']
    app_path = app_config['app_path']
    
    if not os.path.exists(venv_path):
        return False, f"Virtual environment not found: {venv_path}"
    
    if not os.path.exists(app_path):
        return False, f"Application directory not found: {app_path}"
    
    return True, "App directories found."

def get_app_status(app_name, running_processes):
    if app_name in running_processes:
        update_process_status(app_name, running_processes)
        return running_processes[app_name]['status']
    return 'stopped'

def find_and_kill_process_by_port(port):
    for conn in psutil.net_connections():
        if conn.laddr.port == port:
            try:
                process = psutil.Process(conn.pid)
                for child in process.children(recursive=True):
                    child.kill()
                process.kill()
                return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    return False

def force_kill_process_by_name(app_name, app_configs):
    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."

    port = app_config['port']
    killed = find_and_kill_process_by_port(port)

    if killed:
        return True, f"{app_name} processes have been forcefully terminated."
    else:
        return False, f"No running processes found for {app_name} on port {port}."

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

def get_install_status(app_name):
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

# this is the v2 ("fast") version for "download_and_unpack_venv()" - can be (de-)/activated in DEBUG_SETTINGS dict
def download_and_unpack_venv_v2(app_name:str, app_configs:dict, send_websocket_message) -> tuple[bool, str]:
    # load the latest configured DEBUG_SETTINGS from the stored setting of the DEBUG_SETTINGS_FILE
    init_debug_settings() # reload latest DEBUG_SETTINGS
    # as this could overwrite the APP_CONFIGS_MANIFEST_URL, we reload the app_configs global dict
    # from whatever Url is now defined
    init_app_configs() # reload lastest app_configs dict

    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."

    venv_path = app_config['venv_path']
    download_url = app_config['download_url']
    archive_size = app_config['archive_size']
    
    tar_filename = os.path.basename(download_url)
    workspace_dir = '/workspace'
    downloaded_file = os.path.join(workspace_dir, tar_filename)

    write_debug_setting('tar_filename', tar_filename)
    write_debug_setting('download_url', download_url)

    try:
        if DEBUG_SETTINGS['skip_to_github_stage']:
            success, message = clone_application(app_config,send_websocket_message)
            return success, message
        
        save_install_status(app_name, 'in_progress', 0, 'Downloading')
        send_websocket_message('install_log', {'app_name': app_name, 'log': f'Downloading {archive_size / (1024 * 1024):.2f} MB ...'})

        start_time_download = time.time()

        # debug with existing local cached TAR file
        if os.path.exists(downloaded_file):
            write_debug_setting('used_local_tarfile', True) # indicate using cached TAR file
            send_websocket_message('used_local_tarfile', {'app_name': app_name, 'log': f"Used cached local tarfile '{downloaded_file}'"})
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
                        # FILE: /worksapce/bkohya.tar.gz
                        # -------------------------------------------------------------------------------
                        # <---

                        # When ready (last 6 lines):
                        # Download Results:
                        # --->
                        # gid   |stat|avg speed  |path/URI
                        # ======+====+===========+=======================================================
                        # cd57da|OK  |   1.6MiB/s|/workspace/bkohya.tar.gz

                        # Status Legend:
                        # (OK):download completed.
                        # <---

                        download_running_line_pattern = r"\[#(\w+)\s+(\d+\.?\d*)\s*([GMK]iB)/(\d+\.?\d*)\s*([GMK]iB)\((\d+)%\)\s+CN:(\d+)\s+DL:(\d+\.?\d*)\s*([GMK]iB)\s+ETA:(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?\]"
                        
                        # download_finished_line = "cd57da|OK  |   1.6MiB/s|/workspace/bkohya.tar.gz"
                        download_finished_line_pattern = r"([a-fA-F0-9]{6})\|(\w+)\s*\|\s*([\d.]+[GMK]iB/s)\|(.+)"

                        # try to find the download_running_line_pattern
                        match = re.match(download_running_line_pattern, download_line)
                        if match: # download_running_line_pattern
                            gid = match.group(1)                    # e.g., "cd57da"
                            downloaded_size_value = match.group(2)  # e.g., "2.1"
                            downloaded_size_unit = match.group(3)   # e.g., "GiB"
                            total_size_value =  match.group(4)      # e.g., "4.0" (this could replace the 'archive_size' from the manifest)
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
                            #speed = downloaded_size / elapsed_time # bytes/sec
                            #percentage = (downloaded_size / archive_size) * 100
                            #eta = (archive_size - downloaded_size) / speed if speed > 0 else 0 # sec
                            
                            send_websocket_message('install_progress', {
                                'app_name': app_name,
                                'percentage': percentage,
                                'speed': download_rate_formatted, # f"{speed / (1024 * 1024):.2f} MiB/s",
                                'eta': f"{eta:.0f}",
                                'stage': 'Downloading',
                                'downloaded': downloaded_size_formatted # f"{downloaded_size / (1024 * 1024):.2f} MB"
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

            except Exception as e:
                error_msg = f"ERROR in download_and_unpack_venv_v2():download with ARIA2C\ncmdline: '{cmd_line}'\nException: {str(e)}"
                print(error_msg)

                error_message = f"Downloading VENV failed: {download_process.stderr.read() if download_process.stderr else 'Unknown error'}"
                send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
                save_install_status(app_name, 'failed', 0, 'Failed')

                return False, error_message

            ### original (slow) download code
            # response = requests.get(download_url, stream=True)
            # response.raise_for_status()

            # block_size = 8192
            # downloaded_size = 0
            # start_time = time.time()

            # with open(downloaded_file, 'wb') as file:
            #     for chunk in response.iter_content(chunk_size=block_size):
            #         if chunk:
            #             file.write(chunk)
            #             downloaded_size += len(chunk)
            #             current_time = time.time()
            #             elapsed_time = current_time - start_time
                        
            #             if elapsed_time > 0:
            #                 speed = downloaded_size / elapsed_time
            #                 percentage = (downloaded_size / archive_size) * 100
            #                 eta = (archive_size - downloaded_size) / speed if speed > 0 else 0
                            
            #                 send_websocket_message('install_progress', {
            #                     'app_name': app_name,
            #                     'percentage': round(percentage, 2),
            #                     'speed': f"{speed / (1024 * 1024):.2f} MB/s",
            #                     'eta': f"{eta:.0f}",
            #                     'stage': 'Downloading',
            #                     'downloaded': f"{downloaded_size / (1024 * 1024):.2f} MB"
            #                 })

        if not os.path.exists(downloaded_file):
            error_message = f"Downloading VENV failed, file '{downloaded_file}' does not exist, skipping 'Decompression' stage"
            send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
            save_install_status(app_name, 'failed', 0, 'Failed')

            return False, error_message
            
        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Download completed. Starting Verification ...'})
        # we use a 99% progress and indicate 1% for Verification against the files SHA256 hash
        send_websocket_message('install_progress', {'app_name': app_name, 'percentage': 99, 'stage': 'Downloading'})

        total_duration_download = f"{datetime.timedelta(seconds=int(time.time() - start_time_download))}"
        write_debug_setting('total_duration_download', total_duration_download)
        print(f"download did run {total_duration_download} for app '{app_name}'")


        ### VERIFY stage
        #
        # Create TAR from the VENV current directory:
        #   IMPORTANT: cd INTO the folder you want to compress, as we use "." for source folder,
        #   to avoid having the foldername in the TAR file !!!
        #   PV piping is "nice-to-have" and is only used for showing "Progress Values" during compressing
        #
        #       cd /workspace/bkohya
        #       #tar -czf | pv > /workspace/bkohya.tar.gz . (not the smallest TAR)#
        #       tar -cvf - . | gzip -9 - | pv > /workspace/bkohya.tar.gz
        #
        #   afterwards create the SHA256 hash from this TAR with
        #        shasum -a 256 bkohya.tar.gz
        #
        #   also report the uncompressed size from the current VENV directory,
        #   we need that as the 100% base for the progress indicators when uncompressing the TAR


        # verify the downloaded TAR file against its SHA256 hash value from the manifest

        download_sha256_hash = app_config["sha256_hash"].lower() # get the sha256_hash from the app manifest
        file_verified = False

        print(f"getting SHA256 Hash for '{downloaded_file}'")
        successfull_HashGeneration, file_sha256_hash = get_sha256_hash_from_file(downloaded_file)
        
        if successfull_HashGeneration and file_sha256_hash.lower() == download_sha256_hash.lower():
            file_verified = True
            message = f"Downloaded file '{os.path.basename(downloaded_file)}' was successfully (SHA256) verified."
            print(message)
        
        else:
            if successfull_HashGeneration: # the generated SHA256 file hash did not match against the metadata hash 
                error_message = f"The downloaded file '{os.path.basename(downloaded_file)}' has DIFFERENT \nSHA256: {file_sha256_hash} as in the manifest\nFile is possibly corrupted and was DELETED!"
                print(error_message)

                os.remove(downloaded_file) # delete corrupted, downloaded file
           
            
            else: # NOT successful, the hash contains the Exception
                error_msg = file_sha256_hash
                error_message = f"Exception occured while generating the SHA256 hash for '{downloaded_file}':\n{error_msg}"
                print(error_message)

        if not file_verified:
            send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
            save_install_status(app_name, 'failed', 0, 'Failed')

            return False, error_message

        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Verification completed. Starting unpacking ...'})
        send_websocket_message('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Download Complete'})


        ### Decompression Stage (Unpacking the downloaded VENV)
        start_time_unpack = time.time()

        # Ensure the venv directory exists
        os.makedirs(f"{venv_path}/", exist_ok=True) # append trailing "/" to make sure the last sub-folder is created

        # Unpack the tar.gz file
        send_websocket_message('install_progress', {'app_name': app_name, 'percentage': 0, 'stage': 'Unpacking'})


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

        uncompressed_size_bytes = app_config["venv_uncompressed_size"]
        
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
        #     send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
        #     save_install_status(app_name, 'failed', 0, 'Failed')

        #     return False, error_message
        

        ### Stage Unpacking
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

                        ### original code
                        #files_processed += 1
                        #percentage = min(int((files_processed / total_files) * 100), 100)

                        send_websocket_message('install_progress', {
                            'app_name': app_name,
                            'percentage': percentage,
                            'stage': 'Unpacking',
                            'processed': decompression_speed_formatted, # files_processed, # TODO: remove this later, as we not have/need this info
                            'total': "multiple" # total_files # TODO: remove this later, as we not have/need this info
                        })

                        # another summary line (every 1s) for the install_log
                        decompression_progress_details = f"{decompression_time_string} {percentage}% {int(decompression_size_bytes / (1024 * 1024))} / {int(uncompressed_size_bytes / (1024 * 1024))} MiB @ {decompression_speed} {decompression_speed_unit}"
                        
                        send_websocket_message('install_log', {'app_name': app_name, 'log': f"Unpacking: {decompression_progress_details}"})
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
            error_msg = f"ERROR in download_and_unpack_venv_v2():\ncmdline: '{cmd_line}'\nException: {str(e)}"
            print(error_msg)

        decompression_process.wait() # let the process finish
        rc = decompression_process.returncode # and get the return code
        
        total_duration_unpack = f"{datetime.timedelta(seconds=int(time.time() - start_time_unpack))}"
        write_debug_setting('total_duration_unpack', total_duration_unpack)
        print(f"unpack did run {total_duration_unpack} for app '{app_name}'")


        if rc != 0:
            error_message = f"Unpacking failed: {decompression_process.stderr.read() if decompression_process.stderr else 'Unknown error'}"
            send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
            save_install_status(app_name, 'failed', 0, 'Failed')

            return False, error_message
        
        send_websocket_message('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Unpacking Complete'})
        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Unpacking complete. Proceeding to clone repository...'})

        # Clone the repository
        success, message = clone_application(app_config, send_websocket_message)
        if not success:
            return False, message

        # Clean up the downloaded file
        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Cleaning up...'})

        # lutzapps - debug with local TAR
        # do NOT delete the Kohya venv
        if DEBUG_SETTINGS["delete_tar_file_after_download"]: # this is the default, but can be overwritten
            os.remove(downloaded_file)

        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Installation complete. Refresh page to start app'})
        save_install_status(app_name, 'completed', 100, 'Completed')
        send_websocket_message('install_complete', {'app_name': app_name, 'status': 'success', 'message': "Virtual environment installed successfully."})
        return True, "Virtual environment installed successfully."

    except Exception as e:
        error_message = f"Installation failed: {str(e)}\n{traceback.format_exc()}"
        save_install_status(app_name, 'failed', 0, 'Failed')
        send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
        return False, error_message

### installing the App from GITHUB
# Clone the repository if it doesn't exist
def clone_application(app_config:dict, send_websocket_message) -> tuple[bool , str]:
    try:
        app_name = app_config['id']
        app_path = app_config['app_path']

        if not os.path.exists(app_path): # only install new apps           
            repo_url = app_config['repo_url']
            branch_name = app_config['branch_name']
            if branch_name == "": # use the default branch
                branch_name = "master"
            clone_recursive = app_config['clone_recursive']

            send_websocket_message('install_log', {'app_name': app_name, 'log': f"Cloning repository '{repo_url}' branch '{branch_name}' recursive={clone_recursive} ..."})

            repo = git.Repo.clone_from(repo_url, app_path, # first 2 params are fix, then use named params
                #branch=branch_name, # if we provide a branch here, we ONLY get this branch downloaded
                # we want ALL branches, so we can easy checkout different versions from kohya_ss late, without re-downloading
                recursive=clone_recursive, # include cloning submodules recursively (if needed as with Kohya)
                progress=lambda op_code, cur_count, max_count, message: send_websocket_message('install_log', {
                    'app_name': app_name,
                    'log': f"Cloning: {cur_count}/{max_count} {message}"
            }))


            send_websocket_message('install_log', {'app_name': app_name, 'log': 'Repository cloned successfully.'})

            # lutzapps - make sure we use Kohya with FLUX support
            if not branch_name == "master":
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
                if app_name == 'bkohya':
                    success, message = update_kohya_setup_sh(app_path) # patch the 'setup.sh' file
                    print(message) # shows, if the patch was needed, and apllied successfully
        else: # refresh app
            if app_path['refresh']: # app wants auto-refreshes
                # TODO: implement app refreshes via git pull or, in the case of 'kohya_ss' via "setup.sh"
                message = f"Refreshing of app '{app_name}' is NYI"
                print(message)

        # Clone ComfyUI-Manager and other defined custom_nodes for Better ComfyUI
        if app_name == 'bcomfy':
            # install all defined custom nodes
            custom_nodes_path = os.path.join(app_path, 'custom_nodes')
            os.makedirs(f"{custom_nodes_path}/", exist_ok=True) # append a trailing slash to be sure last dir is created
            for custom_node in app_config['custom_nodes']:
                name = custom_node['name']
                path = custom_node['path']
                repo_url = custom_node['repo_url']
                custom_node_path = os.path.join(custom_nodes_path, path)
                
                if not os.path.exists(custom_node_path): # only install new custom nodes
                    send_websocket_message('install_log', {'app_name': app_name, 'log': f"Cloning '{name}' ..."})
                    git.Repo.clone_from(repo_url, custom_node_path)
                    send_websocket_message('install_log', {'app_name': app_name, 'log': f"'{name}' cloned successfully."})

                    # install requirements
                    venv_path = app_config['venv_path']
                    #app_path = app_config['app_path'] # already defined
                    
                    try:
                        # Activate the virtual environment and run the commands
                        activate_venv = f"source {venv_path}/bin/activate"
                        change_dir_command = f"cd {custom_node_path}"
                        pip_install_command = "pip install -r requirements.txt"
                        
                        full_command = f"{activate_venv} && {change_dir_command} && {pip_install_command}"
                        
                        # TODO: rewrite this without shell
                        process = subprocess.Popen(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, executable='/bin/bash')
                        output, _ = process.communicate()
                        
                        if process.returncode == 0:
                            return True, f"Custom node requirements were successfully installed. Output: {output.decode('utf-8')}"
                        else:
                            return False, f"Error in custom node requirements installation. Output: {output.decode('utf-8')}"
                    except Exception as e:
                        return False, f"Error installing custom node requirements: {str(e)}"
                        

    except git.exc.GitCommandError as e:
        send_websocket_message('install_log', {'app_name': app_name, 'log': f'Error cloning repository: {str(e)}'})
        return False, f"Error cloning repository: {str(e)}"
    except Exception as e:
        send_websocket_message('install_log', {'app_name': app_name, 'log': f'Error cloning repository: {str(e)}'})
        return False, f"Error cloning repository: {str(e)}"


    if app_name == 'bkohya': # create a folder link for kohya_ss local "venv"
        success, message = ensure_kohya_local_venv_is_symlinked()
        if not success: # symlink not created, but still success=True and only a warning, can be fixed manually
            message = f"{app_config['name']} was cloned and patched successfully, but the symlink to the local venv returned following problem:\n{message}"
    else:
            message = f"'{app_name}' was cloned successfully."

    return True, message

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

def download_and_unpack_venv_v1(app_name, app_configs, send_websocket_message):
    app_config = app_configs.get(app_name)
    if not app_config:
        return False, f"App '{app_name}' not found in configurations."

    venv_path = app_config['venv_path']
    app_path = app_config['app_path']
    download_url = app_config['download_url']
    archive_size = app_config['size']
    tar_filename = os.path.basename(download_url)
    workspace_dir = '/workspace'
    downloaded_file = os.path.join(workspace_dir, tar_filename)

    try:
        save_install_status(app_name, 'in_progress', 0, 'Downloading')
        send_websocket_message('install_log', {'app_name': app_name, 'log': f'Starting download of {archive_size / (1024 * 1024):.2f} MB...'})

        # lutzapps - debug with existing local TAR
        if not os.path.exists(downloaded_file):
            response = requests.get(download_url, stream=True)
            response.raise_for_status()

            block_size = 8192
            downloaded_size = 0
            start_time = time.time()

            with open(downloaded_file, 'wb') as file:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        file.write(chunk)
                        downloaded_size += len(chunk)
                        current_time = time.time()
                        elapsed_time = current_time - start_time
                        
                        if elapsed_time > 0:
                            speed = downloaded_size / elapsed_time
                            percentage = (downloaded_size / archive_size) * 100
                            eta = (archive_size - downloaded_size) / speed if speed > 0 else 0
                            
                            send_websocket_message('install_progress', {
                                'app_name': app_name,
                                'percentage': round(percentage, 2),
                                'speed': f"{speed / (1024 * 1024):.2f} MB/s",
                                'eta': f"{eta:.0f}",
                                'stage': 'Downloading',
                                'downloaded': f"{downloaded_size / (1024 * 1024):.2f} MB"
                            })

        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Download completed. Starting unpacking...'})
        send_websocket_message('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Download Complete'})
        
        # Ensure the venv directory exists
        os.makedirs(venv_path, exist_ok=True)

        # Unpack the tar.gz file
        send_websocket_message('install_progress', {'app_name': app_name, 'percentage': 0, 'stage': 'Unpacking'})

        # lutzapps - fix TAR bug (compressed from the workspace root instead of bbkohya)
        # e.g. "bkohya/bin/activate", together with venv_path ("/workspace/bkohya") ends up as "/workspace/bkohya/bkohya/nin/activate"
        if app_name == "bkohya":
            venv_path = "/workspace"        

        unpack_command = f"tar -xzvf {downloaded_file} -C {venv_path}"
        process = subprocess.Popen(unpack_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        
        total_files = sum(1 for _ in subprocess.Popen(f"tar -tvf {downloaded_file}", shell=True, stdout=subprocess.PIPE).stdout)
        files_processed = 0
        
        for line in process.stdout:
            files_processed += 1
            percentage = min(int((files_processed / total_files) * 100), 100)
            send_websocket_message('install_progress', {
                'app_name': app_name,
                'percentage': percentage,
                'stage': 'Unpacking',
                'processed': files_processed,
                'total': total_files
            })
            send_websocket_message('install_log', {'app_name': app_name, 'log': f"Unpacking: {line.strip()}"})
        
        process.wait()
        if process.returncode != 0:
            error_message = f"Unpacking failed: {process.stderr.read() if process.stderr else 'Unknown error'}"
            send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
            save_install_status(app_name, 'failed', 0, 'Failed')
            return False, error_message
        
        send_websocket_message('install_progress', {'app_name': app_name, 'percentage': 100, 'stage': 'Unpacking Complete'})

        # Clone the repository if it doesn't exist
        if not os.path.exists(app_path):
            send_websocket_message('install_log', {'app_name': app_name, 'log': 'Cloning repository...'})
            
            repo_url = ''
            if app_name == 'bcomfy':
                repo_url = 'https://github.com/comfyanonymous/ComfyUI.git'
            elif app_name == 'bforge':
                repo_url = 'https://github.com/lllyasviel/stable-diffusion-webui-forge.git'
            elif app_name == 'ba1111':
                repo_url = 'https://github.com/AUTOMATIC1111/stable-diffusion-webui.git'
            elif app_name == 'bkohya': # lutzapps - added new Kohya app
                repo_url = 'https://github.com/bmaltais/kohya_ss.git'
            
            try: # add a repo assignment for Kohya
                repo = git.Repo.clone_from(repo_url, app_path, progress=lambda op_code, cur_count, max_count, message: send_websocket_message('install_log', {
                    'app_name': app_name,
                    'log': f"Cloning: {cur_count}/{max_count} {message}"
                }))
                send_websocket_message('install_log', {'app_name': app_name, 'log': 'Repository cloned successfully.'})

                # lutzapps - make sure we use Kohya with FLUX support
                if app_name == 'bkohya':
                    branch_name = "sd3-flux.1" # this branch also uses a "sd-scripts" branch "SD3" automatically
                    repo.git.checkout(branch_name)

                # Clone ComfyUI-Manager for Better ComfyUI
                if app_name == 'bcomfy':
                    custom_nodes_path = os.path.join(app_path, 'custom_nodes')
                    os.makedirs(custom_nodes_path, exist_ok=True)
                    comfyui_manager_path = os.path.join(custom_nodes_path, 'ComfyUI-Manager')
                    if not os.path.exists(comfyui_manager_path):
                        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Cloning ComfyUI-Manager...'})
                        git.Repo.clone_from('https://github.com/ltdrdata/ComfyUI-Manager.git', comfyui_manager_path)
                        send_websocket_message('install_log', {'app_name': app_name, 'log': 'ComfyUI-Manager cloned successfully.'})

            except git.exc.GitCommandError as e:
                send_websocket_message('install_log', {'app_name': app_name, 'log': f'Error cloning repository: {str(e)}'})
                return False, f"Error cloning repository: {str(e)}"

        # Clean up the downloaded file
        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Cleaning up...'})

        # lutzapps - debug with local TAR
        # do NOT delete the Kohya venv
        #os.remove(downloaded_file)

        send_websocket_message('install_log', {'app_name': app_name, 'log': 'Installation complete. Refresh page to start app'})

        save_install_status(app_name, 'completed', 100, 'Completed')
        send_websocket_message('install_complete', {'app_name': app_name, 'status': 'success', 'message': "Virtual environment installed successfully."})
        return True, "Virtual environment installed successfully."
    except requests.RequestException as e:
        error_message = f"Download failed: {str(e)}"
        send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
        save_install_status(app_name, 'failed', 0, 'Failed')
        return False, error_message
    except Exception as e:
        error_message = f"Installation failed: {str(e)}\n{traceback.format_exc()}"
        save_install_status(app_name, 'failed', 0, 'Failed')
        send_websocket_message('install_complete', {'app_name': app_name, 'status': 'error', 'message': error_message})
        return False, error_message

### this is the function which switches between v0 and v1 debug setting for comparison
def download_and_unpack_venv(app_name:str, app_configs:dict, send_websocket_message) -> tuple[bool, str]:
    from utils.app_configs import DEBUG_SETTINGS, write_debug_setting

    installer_codeversion = DEBUG_SETTINGS['installer_codeversion'] # read from DEBUG_SETTINGS
    print(f"download_and_unpack_venv_{installer_codeversion} STARTING for '{app_name}'")

    import time

    start_time = time.time()
          
    if installer_codeversion == "v1":
        success, message = download_and_unpack_venv_v1(app_name, app_configs, send_websocket_message)
    elif installer_codeversion == "v2":
        success, message = download_and_unpack_venv_v2(app_name, app_configs, send_websocket_message)
    else:
        error_msg = f"unknown 'installer_codeversion' {installer_codeversion} found, nothing run for app '{app_name}'"
        print(error_msg)
        success = False
        message = error_msg

    total_duration = f"{datetime.timedelta(seconds=int(time.time() - start_time))}"

    write_debug_setting('app_name', app_name)
    write_debug_setting('total_duration', total_duration)

    print(f"download_and_unpack_venv_v{installer_codeversion} did run {total_duration} for app '{app_name}'")
    return success, message

def fix_custom_nodes(app_name, app_configs):
    if app_name != 'bcomfy':
        return False, "This operation is only available for Better ComfyUI."
    
    venv_path = app_configs['bcomfy']['venv_path']
    app_path = app_configs['bcomfy']['app_path']
    
    try:
        # Activate the virtual environment and run the commands
        activate_venv = f"source {venv_path}/bin/activate"
        set_default_command = f"comfy --skip-prompt --no-enable-telemetry set-default {app_path}"
        restore_dependencies_command = "comfy node restore-dependencies"
        
        full_command = f"{activate_venv} && {set_default_command} && {restore_dependencies_command}"
        
        process = subprocess.Popen(full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, executable='/bin/bash')
        output, _ = process.communicate()
        
        if process.returncode == 0:
            return True, f"Custom nodes fixed successfully. Output: {output.decode('utf-8')}"
        else:
            return False, f"Error fixing custom nodes. Output: {output.decode('utf-8')}"
    except Exception as e:
        return False, f"Error fixing custom nodes: {str(e)}"

# Replace the existing install_app function with this updated version
def install_app(app_name:str, app_configs:dict, send_websocket_message) -> tuple[bool, str]:
    if app_name in app_configs:
        success, message = download_and_unpack_venv(app_name, app_configs, send_websocket_message)
        return success, message
    else:
        return False, f"Unknown app: {app_name}"
