import os
import requests
from urllib.parse import unquote, urlparse
from tqdm import tqdm
import json
import re
import time
import math
### model_utils-v0.2 by lutzapps, Oct 30th 2024 ###
# lutzapps - modify for new shared_models module and overwrite for this module
from utils.shared_models import (ensure_shared_models_folders, update_model_symlinks, SHARED_MODELS_DIR)
from utils.websocket_utils import send_websocket_message, active_websockets

#SHARED_MODELS_DIR = '/workspace/shared_models' # this global var is now owned by the 'shared_models' module

# lutzapps - modify this CivitAI model_type mapping to the new SHARED_MODEL_FOLDERS map
MODEL_TYPE_MAPPING = {
    # CivitAI-Modeltype: SHARED_MODEL_FOLDERS
    'Checkpoint': 'ckpt', #'Stable-diffusion', # not clear name for model_type
    'LORA': 'loras', #'Lora', # now lowercase and plural
    'LoCon': 'loras', #'Lora', # now lowercase and plural
    'TextualInversion': 'embeddings',
    'VAE': 'vae', #'VAE', # now lowercase
    'Hypernetwork': 'hypernetworks',
    'AestheticGradient': 'embeddings', #'aesthetic_embeddings', # store together with "embeddings"
    'ControlNet': 'controlnet',
    'Upscaler': 'upscale_models' #'ESRGAN' # there are probably other upscalers not based on ESRGAN
}

def ensure_shared_folder_exists():
    # lutzapps - replace with new shared_models code
    #for folder in ['Stable-diffusion', 'Lora', 'embeddings', 'VAE', 'hypernetworks', 'aesthetic_embeddings', 'controlnet', 'ESRGAN']:
    #    os.makedirs(os.path.join(SHARED_MODELS_DIR, folder), exist_ok=True)
    ensure_shared_models_folders()

def check_civitai_url(url):
    prefix = "civitai.com"
    try:
        if prefix in url:
            if "civitai.com/api/download" in url:
                version_id = url.strip("/").split("/")[-1]
                return False, True, None, int(version_id)
            
            subpath = url[url.find(prefix) + len(prefix):].strip("/")
            url_parts = subpath.split("?")
            if len(url_parts) > 1:
                model_id = url_parts[0].split("/")[1]
                version_id = url_parts[1].split("=")[1]
                return True, False, int(model_id), int(version_id)
            else:
                model_id = subpath.split("/")[1]
                return True, False, int(model_id), None
    except (ValueError, IndexError):
        print("Error parsing Civitai model URL")
    return False, False, None, None

def check_huggingface_url(url):
    parsed_url = urlparse(url)
    if parsed_url.netloc not in ["huggingface.co", "huggingface.com"]:
        return False, None, None, None, None
    
    path_parts = [p for p in parsed_url.path.split("/") if p]
    if len(path_parts) < 5 or (path_parts[2] != "resolve" and path_parts[2] != "blob"):
        return False, None, None, None, None
    
    repo_id = f"{path_parts[0]}/{path_parts[1]}"
    branch_name = path_parts[3]
    remaining_path = "/".join(path_parts[4:])
    folder_name = os.path.dirname(remaining_path) if "/" in remaining_path else None
    filename = unquote(os.path.basename(remaining_path))
    
    return True, repo_id, filename, folder_name, branch_name

def download_model(url, model_name, model_type, civitai_token=None, hf_token=None, version_id=None, file_index=None) -> tuple[bool, str]:
    ensure_shared_folder_exists()
    is_civitai, is_civitai_api, model_id, _ = check_civitai_url(url)
    is_huggingface, repo_id, hf_filename, hf_folder_name, hf_branch_name = check_huggingface_url(url) # TODO: double call

    if is_civitai or is_civitai_api:
        if not civitai_token:
            return False, "Civitai token is required for downloading from Civitai"
        success, message = download_civitai_model(url, model_name, model_type, civitai_token, version_id, file_index)
    elif is_huggingface:
        success, message = download_huggingface_model(url, model_name, model_type, repo_id, hf_filename, hf_folder_name, hf_branch_name, hf_token)
    else:
        return False, "Unsupported URL"

    if success:
        send_websocket_message('model_download_progress', {
            'percentage': 100,
            'stage': 'Complete',
            'message': 'Download complete and symlinks updated'
        })
    
    return success, message

# lutzapps - added SHA256 checks for already existing ident and downloaded HuggingFace model
def download_civitai_model(url, model_name, model_type, civitai_token, version_id=None, file_index=None) -> tuple[bool, str]:
    try:
        is_civitai, is_civitai_api, model_id, url_version_id = check_civitai_url(url)
        
        headers = {'Authorization': f'Bearer {civitai_token}'}
        
        if is_civitai_api:
            api_url = f"https://civitai.com/api/v1/model-versions/{url_version_id}"
        else:
            api_url = f"https://civitai.com/api/v1/models/{model_id}"
        
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        model_data = response.json()
        
        if is_civitai_api:
            version_data = model_data
            model_data = version_data['model']
        else:
            if version_id:
                version_data = next((v for v in model_data['modelVersions'] if v['id'] == version_id), None)
            elif url_version_id:
                version_data = next((v for v in model_data['modelVersions'] if v['id'] == url_version_id), None)
            else:
                version_data = model_data['modelVersions'][0]
            
            if not version_data:
                return False, f"Version ID {version_id or url_version_id} not found for this model."
        
        civitai_model_type = model_data['type']
        model_type = MODEL_TYPE_MAPPING.get(civitai_model_type, 'Stable-diffusion')
        
        files = version_data['files']
        if file_index is not None and 0 <= file_index < len(files):
            file_to_download = files[file_index]
        elif len(files) > 1:
            # If there are multiple files and no specific file was chosen, ask the user to choose
            file_options = [{'name': f['name'], 'size': f['sizeKB'], 'type': f['type']} for f in files]
            return True, {
                'choice_required': {
                    'type': 'file',
                    'model_id': model_id,
                    'version_id': version_data['id'],
                    'files': file_options
                }
            }
        else:
            civitai_file = files[0] # that is the metadata civitai_file

        download_url = civitai_file['downloadUrl']
        if not model_name:
            model_name = civitai_file['name']

        model_path = os.path.join(SHARED_MODELS_DIR, model_type, model_name)

        platformInfo = {
            "platform_name": 'civitai',
            "civitai_file": civitai_file # civitai_file metadata dictionary
        }
        # call shared function for "huggingface" and "civitai" for SHA256 support and "Model Downloader UI" extended support
        download_sha256_hash, found_ident_local_model, message = get_modelfile_hash_and_ident_existing_modelfile_exists(
            model_name, model_type, model_path, # pass local workspace vars, then platform specific vars as dictionary
            platformInfo) # [str, bool, str]

        if found_ident_local_model:
            return True, message

        # model_path does NOT exist - run with original code

        os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
        # lutzapps - add SHA256 check for download_sha256_hash is handled after download finished in download_file()
        return download_file(download_url, download_sha256_hash, model_path, headers) # [bool, str]
    
    except Exception as e: # requests.RequestException as e:

        return False, f"Exception downloading from CivitAI: {str(e)}"


# lutzapps - calculate the SHA256 hash string of a file
def get_sha256_hash_from_file(file_path:str) -> tuple[bool, str]:
    import hashlib # support SHA256 checks

    try:
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            # read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return True, sha256_hash.hexdigest().lower()
    
    except Exception as e:
        return False, str(e)


# lutzapps - support SHA256 Hash check of already locally existing modelfile against its metadata hash before downloading is needed
# shared function for "huggingface" and "civitai" called by download_huggingface_model() and download_civitai_model()
def get_modelfile_hash_and_ident_existing_modelfile_exists(model_name:str, model_type:str, model_path:str, platformInfo:dict) -> tuple[bool, str, str]:
    try:
        # update (and remember) the selected index of the modelType select list of the "Model Downloader"
        message = f"Select the ModelType '{model_type}' to download"
        print(message)

        send_websocket_message('extend_ui_helper', {
            'cmd': 'selectModelType',
            'model_type': f'{model_type}', # e.g. "loras" or "vae"
            'message': message
        } )

        # get the SHA256 hash - used for compare against existing or downloaded model
        platform_name = platformInfo['platform_name'].lower() # currently "civitai" or "huggingface", but could be extendend
        print(f"\nPlatform: {platform_name}")

        match platform_name:
            case "huggingface":
                # get the platform-specific passed variables for "huggingface"
                hf_token = platformInfo['hf_token']
                repo_id = platformInfo['repo_id']
                hf_filename = platformInfo['hf_filename']

                #from huggingface_hub import hf_hub_download
                # lutzapps - to get SHA256 hash from model
                from huggingface_hub import (
                    # HfApi, # optional when not calling globally
                    get_paths_info #list_files_info #DEPRECATED/MISSING: list_files_info => get_paths_info
                )
                from huggingface_hub.hf_api import (
                    RepoFile, RepoFolder, BlobLfsInfo
                )

                ## optionally configure a HfApi client instead of calling globally
                # hf_api = HfApi(
                #     endpoint = "https://huggingface.co", # can be a Private Hub endpoint
                #     token = hf_token, # token is not persisted on the machine
                # )

                print(f"getting SHA256 Hash for '{model_name}' from repo {repo_id}/{hf_filename}")
                # HfApi.list_files_info deprecated -> HfApi.get_paths_info (runs into exception, as connot be imported as missing)
                #files_info = hf_api.list_files_info(repo_id, hf_filename, expand=True)
                #paths_info = hf_api.get_paths_info(repo_id, hf_filename, expand=True) # use via HfApi
                paths_info = get_paths_info(repo_id, hf_filename, expand=True) # use global (works fine)

                repo_file = paths_info[0] # RepoFile or RepoFolder class instance
                # check for RepoFolder or NON-LFS
                if isinstance(repo_file, RepoFolder):
                    raise NotImplementedError("Downloading a folder is not implemented.")
                if not repo_file.lfs:
                    raise NotImplementedError("Copying a non-LFS file is not implemented.")
                
                lfs = repo_file.lfs # BlobLfsInfo class instance
                download_sha256_hash = lfs.sha256.lower()

                print(f"Metadata from RepoFile LFS '{repo_file.rfilename}'")
                print(f"SHA256: {download_sha256_hash}")

            case "civitai":
                # get the platform-specific passed variables for "civitai"
                civitai_file = platformInfo['civitai_file'] # civitai_file metadata dictionary

                # get the SHA256 hash - used for compare against existing or downloaded model
                download_sha256_hash = civitai_file['hashes']['SHA256'] # civitai_file = passed file
    
        ### END platform specific code

        # check if model file already exists
        if not os.path.exists(model_path):
            message = f"No local model '{os.path.basename(model_path)}' installed"
            print(message)

            return download_sha256_hash, False, message
        
        message = f"Model already exists: {os.path.basename(model_path)}, SHA256 check..."
        print(message)

        send_websocket_message('model_download_progress', {
            'percentage': 0, # ugly
            'stage': 'Downloading',
            'message': message
        })

        # check if existing model is ident with model to download
        # this can *take a while* for big models, but even better than to unnecessarily redownload the model
        successfull_HashGeneration, model_sha256_hash = get_sha256_hash_from_file(model_path)
        # if NOT successful, the hash contains the Exception
        print(f"SHA256 hash generated from local file: '{model_path}'\n{model_sha256_hash}")
        
        if successfull_HashGeneration and model_sha256_hash.lower() == download_sha256_hash.lower():
            message = f"Existing and ident model already found for '{os.path.basename(model_path)}'"
            print(message)

            send_websocket_message('model_download_progress', {
                'percentage': 100,
                'stage': 'Complete',
                'message': message
            })

            return download_sha256_hash, successfull_HashGeneration, message
        
        else:
            if successfull_HashGeneration: # the generated SHA256 file model Hash did not match against the metadata hash 
                message = f"Local installed model '{os.path.basename(model_path)}' has DIFFERENT \nSHA256: {model_sha256_hash}"
                print(message)

                return download_sha256_hash, False, message
            
            
            else: # NOT successful, the hash contains the Exception
                error_msg = model_sha256_hash
                error_msg = f"Exception occured while generating the SHA256 hash for '{model_path}':\n{error_msg}"
                print(error_msg)

    except Exception as e:
        error_msg = f"Exception when downloading from {platform_name}: {str(e)}"
    
    return "", False, error_msg # hash, identfile, message


# lutzapps - added SHA256 checks for already existing ident and downloaded HuggingFace model
def download_huggingface_model(url, model_name, model_type, repo_id, hf_filename, hf_folder_name, hf_branch_name, hf_token=None) -> tuple[bool, str]:
    try:
        from huggingface_hub import hf_hub_download

        if not model_name:
            model_name = hf_filename
        
        model_path = os.path.join(SHARED_MODELS_DIR, model_type, model_name)

        platformInfo = {
            "platform_name": 'huggingface',
            "hf_token": hf_token,
            "repo_id": repo_id,
            "hf_filename": hf_filename
        }
        # call shared function for "huggingface" and "civitai" for SHA256 support and "Model Downloader UI" extended support
        download_sha256_hash, found_ident_local_model, message = get_modelfile_hash_and_ident_existing_modelfile_exists(
            model_name, model_type, model_path, # pass local workspace vars, then platform specific vars as dictionary
            platformInfo) # [str, bool, str]
        
        if found_ident_local_model:
            return True, message
        
        # model_path does NOT exist - run with original code

        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        send_websocket_message('model_download_progress', {
            'percentage': 0,
            'stage': 'Downloading',
            'message': f'Starting download from Hugging Face: {repo_id}'
        })
        
        kwargs = {
            'repo_id': repo_id,
            'filename': hf_filename,
            'subfolder': hf_folder_name,
            'revision': hf_branch_name,
            'local_dir': os.path.dirname(model_path)
            #'local_dir_use_symlinks': False # deprecated, should be removed
        }
        if hf_token:
            kwargs['token'] = hf_token
        
        file_path = hf_hub_download(**kwargs) ### HF_DOWNLOAD_START
        ### HF_DOWNLOAD COMPLETE

        # SHA256 Hash checks of downloaded modelfile against its metadata hash
        # call shared function for "huggingface" and "civitai" for SHA256 support and "Model Downloader UI" extended support
        return check_downloaded_modelfile(file_path, download_sha256_hash, "huggingface") # [bool, str]

    except Exception as e:

        return False, f"Exception when downloading from 'HuggingFace': {str(e)}"


# lutzapps - added SHA256 check for downloaded CivitAI model
def download_file(url, download_sha256_hash, file_path, headers=None) -> tuple[bool, str]:
    try:
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded_size = 0
        start_time = time.time()
        
        with open(file_path, 'wb') as file: ### CIVITAI_DOWNLOAD
            for data in response.iter_content(block_size):
                size = file.write(data)
                downloaded_size += size
                current_time = time.time()
                elapsed_time = current_time - start_time
                
                if elapsed_time > 0:
                    speed = downloaded_size / elapsed_time
                    percentage = (downloaded_size / total_size) * 100 if total_size > 0 else 0
                    eta = (total_size - downloaded_size) / speed if speed > 0 else 0
                    
                    send_websocket_message('model_download_progress', {
                        'percentage': round(percentage, 2),
                        'speed': f"{speed / (1024 * 1024):.2f} MB/s",
                        'eta': int(eta),
                        'stage': 'Downloading',
                        'message': f'Downloaded {format_size(downloaded_size)} / {format_size(total_size)}'
                    })

        ### CIVITAI_DOWNLOAD COMPLETE

        # SHA256 Hash checks of downloaded modelfile against its metadata hash
        # call shared function for "huggingface" and "civitai" for SHA256 support and "Model Downloader UI" extended support
        return check_downloaded_modelfile(file_path, download_sha256_hash, "civitai") # [bool, str]
    
    except Exception as e:
        return False, f"Exception when downloading from CivitAI: {str(e)}"

# lutzapps - SHA256 Hash checks of downloaded modelfile against its metadata hash
# shared function for "huggingface" and "civitai" for SHA256 support and "Model Downloader UI" extended support
def check_downloaded_modelfile(model_path:str, download_sha256_hash:str, platform_name:str) -> tuple[bool, str]:
    try:
        # lutzapps - SHA256 check for download_sha256_hash
        if download_sha256_hash == "":
            
            return False, f"Downloaded model could not be verified with Metadata, no SHA256 hash found on '{platform_name}'"

        # check if downloaded local model file is ident with HF model download_sha256_hash metadata
        # this can take a while for big models, but even better than to have a corrupted model
        send_websocket_message('model_download_progress', {
            'percentage': 90, # change back from 100 to 90 (ugly)
            'stage': 'Complete', # leave it as 'Complete' as this "clears" SPEED/ETA Divs
            'message': f'SHA256 Check for Model: {os.path.basename(model_path)}'
        })

        successfull_HashGeneration, model_sha256_hash = get_sha256_hash_from_file(model_path)
        if successfull_HashGeneration and model_sha256_hash.lower() == download_sha256_hash.lower():
            send_websocket_message('model_download_progress', {
                'percentage': 100,
                'stage': 'Complete',
                'message': f'Download complete: {os.path.basename(model_path)}'
            })

            update_model_symlinks() # create symlinks for this new downloaded model for all installed apps

            return True, f"Successfully downloaded (SHA256 checked, and symlinked) '{os.path.basename(model_path)}' from {platform_name}"
        
        else:
            if successfull_HashGeneration: # the generated SHA256 file model Hash did not match against the metadata hash 
                message = f"The downloaded model '{os.path.basename(model_path)}' has DIFFERENT \nSHA256: {model_sha256_hash} as stored on {platform_name}\nFile is possibly corrupted and was DELETED!"
                print(message)

                os.remove(model_path) # delete corrupted, downloaded file
                
                return download_sha256_hash, False, message
                        
            else: # NOT successful, the hash contains the Exception
                error_msg = model_sha256_hash
                error_msg = f"Exception occured while generating the SHA256 hash for '{model_path}':\n{error_msg}"
                print(error_msg)
    
    except Exception as e:
        error_msg = f"Exception when downloading from {platform_name}: {str(e)}"

    return False, error_msg


# smaller helper functions
def get_civitai_file_size(url, token):
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.head(url, headers=headers, allow_redirects=True)
        return int(response.headers.get('content-length', 0))
    except:
        return None

def get_huggingface_file_size(repo_id, filename, folder_name, branch_name, token):
    from huggingface_hub import hf_hub_url, HfApi
    try:
        api = HfApi()
        file_info = api.hf_hub_url(repo_id, filename, subfolder=folder_name, revision=branch_name)
        response = requests.head(file_info, headers={'Authorization': f'Bearer {token}'} if token else None)
        return int(response.headers.get('content-length', 0))
    except:
        return None

def format_size(size_in_bytes):
    if size_in_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_in_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_in_bytes / p, 2)
    return f"{s} {size_name[i]}"
