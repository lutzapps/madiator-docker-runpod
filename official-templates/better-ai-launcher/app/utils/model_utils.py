import os
import requests
from urllib.parse import unquote, urlparse
from tqdm import tqdm
import json
import re
import time
import math
# lutzapps - modify for new shared_models module and overwrite for this module
from shared_models import (ensure_shared_models_folders, SHARED_MODELS_DIR)

#SHARED_MODELS_DIR = '/workspace/shared_models'

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

def download_model(url, model_name, model_type, send_websocket_message, civitai_token=None, hf_token=None, version_id=None, file_index=None):
    ensure_shared_folder_exists()
    is_civitai, is_civitai_api, model_id, _ = check_civitai_url(url)
    is_huggingface, repo_id, hf_filename, hf_folder_name, hf_branch_name = check_huggingface_url(url)

    if is_civitai or is_civitai_api:
        if not civitai_token:
            return False, "Civitai token is required for downloading from Civitai"
        success, message = download_civitai_model(url, model_name, model_type, send_websocket_message, civitai_token, version_id, file_index)
    elif is_huggingface:
        success, message = download_huggingface_model(url, model_name, model_type, send_websocket_message, repo_id, hf_filename, hf_folder_name, hf_branch_name, hf_token)
    else:
        return False, "Unsupported URL"

    if success:
        send_websocket_message('model_download_progress', {
            'percentage': 100,
            'stage': 'Complete',
            'message': 'Download complete and symlinks updated'
        })
    
    return success, message

def download_civitai_model(url, model_name, model_type, send_websocket_message, civitai_token, version_id=None, file_index=None):
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
            file_to_download = files[0]
        
        download_url = file_to_download['downloadUrl']
        if not model_name:
            model_name = file_to_download['name']
        
        model_path = os.path.join(SHARED_MODELS_DIR, model_type, model_name)
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        return download_file(download_url, model_path, send_websocket_message, headers)
    
    except requests.RequestException as e:
        return False, f"Error downloading from Civitai: {str(e)}"

def download_huggingface_model(url, model_name, model_type, send_websocket_message, repo_id, hf_filename, hf_folder_name, hf_branch_name, hf_token=None):
    try:
        from huggingface_hub import hf_hub_download
        
        if not model_name:
            model_name = hf_filename
        
        model_path = os.path.join(SHARED_MODELS_DIR, model_type, model_name)
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
            'local_dir': os.path.dirname(model_path),
            'local_dir_use_symlinks': False
        }
        if hf_token:
            kwargs['token'] = hf_token
        
        local_file = hf_hub_download(**kwargs)
        
        send_websocket_message('model_download_progress', {
            'percentage': 100,
            'stage': 'Complete',
            'message': f'Download complete: {model_name}'
        })
        
        return True, f"Successfully downloaded {model_name} from Hugging Face"
    
    except Exception as e:
        return False, f"Error downloading from Hugging Face: {str(e)}"

def download_file(url, filepath, send_websocket_message, headers=None):
    try:
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192
        downloaded_size = 0
        start_time = time.time()
        
        with open(filepath, 'wb') as file:
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
        
        send_websocket_message('model_download_progress', {
            'percentage': 100,
            'stage': 'Complete',
            'message': f'Download complete: {os.path.basename(filepath)}'
        })
        
        return True, f"Successfully downloaded {os.path.basename(filepath)}"
    
    except requests.RequestException as e:
        return False, f"Error downloading file: {str(e)}"

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
