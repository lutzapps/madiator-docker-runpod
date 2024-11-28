# better-ai-launcher
Better AI Launcher Image for RunPod and local development.

## RunPod Better App Manager
  
Welcome to the RunPod Better App Manager!  
This image allows you to easily manage and run various AI applications on your RunPod instance.
    
### Features
- Easy installation of pre-configured AI applications.
- Start, Stop, Delete, Check, Refresh and monitor running applications.
- Multiple Versions per App can be selected.
- View application logs in real-time.
- Force kill applications if needed.
- Download Manager for **HuggingFace** and **CivitAI** with `token` support for privat and gated models.
- Shared Models Management for **Downloading and Sharing all models of all types to all installed AI applications**!
    
### Supported Applications
- Better ComfyUI
- Better Forge
- Better A1111
- Better Kohya
- more Apps are planned (AI Trainer `ai-toolkit` and `joy-caption-batch` captioner)
    
### Getting Started
- Access the Better App Manager interface through your RunPod instance URL.
- Install the desired application by clicking the **Install** button.
- Once installed, use the **Start** button to launch the application.
- Access the running application using the **Open App** button.

### Troubleshooting
If you encounter any issues:
- Check the application logs for error messages.
- Try stopping and restarting the application.
- Use the `Force Kill` option if an application becomes unresponsive.
- Refer to the RunPod documentation or contact support for further assistance.
    
For more detailed information and guides, please visit the <a href="https://docs.runpod.io/">RunPod Documentation</a>.


Part of the `madiator-docker-runpod` familiy of **RunPod Docker Containers for RunPod**

## Github
https://github.com/kodxana/madiator-docker-runpod<br>
found under the directory `official-templates/better-ai-launcher`

## Build Options
To build with default options, run `docker buildx bake`, to build a specific target, run `docker buildx bake <target>`.

### Build Vars (based on bake selection)
BASE_IMAGE=`$BASE_IMAGE`, e.g.<br>
BASE_IMAGE=madiator2011/better-base:cuda12.4


## Ports (System)

- 22/tcp (SSH)
- 7222/http (App-Manager)
- 7777/http (VSCode-Server)
- 8181/http (File-Browser)

## Ports (Apps)

- 3000/http (ComfyUI)<br>
- 7862/http (Forge) aka Stable-Diffiusion-WebUI-Forge<br>
- 7863/http (A1111) aka Stable-Diffiusion-WebUI<br>

**New**:
- [6006/http] tensorboard (supporting kohya_ss) - provided at the '/tensorboard/' sub-url
- [7864/http] kohya-ss with FLUX.1 support - provided as a gradio link<br>
`Kohya` is currently configured to run via a `public gradio link` (*.gradio.live domain)<br>
`Tensorboard` currently is pre-started with bkohya and available at `http://localhost:6006/tensorboard/`<br>
**Note**: Both Urls will be automatically opened, wenn you click the `Open Application` button.<br>
Make sure to disable popup-blocker settings in your browser for these 2 additional domains!

## ENV Vars (System)

These ENV vars go into the docker container to support local debugging:<br>
see also explanantion in `".vscode/tasks.json"` or `"docker-compose.debug.yml"`

- LOCAL_DEBUG=True

    change app to localhost Urls and local Websockets (unsecured) for local debugging.<br>
    **TODO**: need to also setup a `bind workspace` in `".vscode/tasks.json"` or `"docker-compose.debug.yml"`

    if you **NOT** want need this behaviour, then set `LOCAL_DEBUG=False` [default],<br>
    which is the same as NOT setting this ENV var at all.

- FLASK_ENV=development

    changed from "`production`" [default].<br>
    only needed when `LOCAL_DEBUG=True`, otherwise this ENV var can be obmitted.

- GEVENT_SUPPORT=True

    gevent monkey-patching is being used, enable gevent support in the debugger.<br>
    only needed when `LOCAL_DEBUG=True`, otherwise this ENV var can be obmitted.

- GIT_PYTHON_TRACE=full

    enables full logging for the GitPython code, used for cloning the apps,<br>
    bcomfy custom_nodes, and refreshing the apps via git fetch/merge = git pull.

- FLASK_DEBUG=0

    "1" allows debugging in Chrome, but then the VSCode debugger will not works.<br>
    "0" is the [default], which is the same as NOT setting this ENV var at all. 

## APP specific Vars
- DISABLE_PULLBACK_MODELS=False

    The default is, that app model files, which are found locally (in only one app), get automatically `pulled-back` into the `"/workspace/shared_models"` folder.<br>
    From there they will be re-linked back not only to their own `pulled-back` model-type folder, but also will be linked back into all other corresponding app model-type folders.<br>
    So the `pulled-back` model is automatically shared to all installed apps.

    If you **NOT** want this behaviour, then set `DISABLE_PULLBACK_MODELS=True`,<br>
    otherwise set `DISABLE_PULLBACK_MODELS=False` [default], which is the same as NOT setting this ENV var at all.

## APP specific USER Vars
All apps can be provisioned in at least 2 Virtual Environment versions:<br>
- 'official' -  This setup is "to the point' as defined and recommended by the app owners on GitHub.<br>
- 'latest' -    This setup extends the 'official' Setup with the latest PyTorch and Cuda libraries, or<br>
                - in the case of ComfyUI - provides also an additional set of pre-installed Custom-Nodes.

The user can choose from all available versions during Setup, or pre-select the VENV_VERSION, which should be installed via following ENV vars in the format `VENV_VERSION_<app_id>`.

If these ENV vars are not set/passed into the container, the App-Manager will provide an UI for selecting them during Setup:

BCOMFY 'official' 5.43 GB (APP 75.3 MB):<br>

    Python 3.11 && Cuda 12.4 && Recommended torch-2.5.1+cu124-cp311-cp311-linux_x86_64 && ComfyUI-Manager && comfy CLI

BCOMFY 'latest' 6.59 GB (APP 400.22 MB):<br>

    Python 3.11 && Cuda 12.4 && Recommended torch-2.5.1+cu124-cp311-cp311-linux_x86_64 && ComfyUI-Manager && comfy CLI && 12x Custom Nodes (see below)

BFORGE 'official' 6.41 GB (APP 106.31 MB):<br>

    Python 3.11 && Cuda 12.1 && Recommended torch-2.3.1+cu121-cp311-cp311-linux_x86_64

BFORGE 'latest' 6.62 GB (APP 105.58 MB):<br>

    Python 3.11 && Cuda 12.4 && Upgraded to torch-2.5.1+cu124-cp311-cp311-linux_x86_64 && xformers

BA111 'official' 4.85 GB (APP 41.78 MB):<br>

    Python 3.11 && Cuda 12.1 && Recommended torch-2.1.2+cu121-cp311-cp311-linux_x86_64

BA111 'latest' 5.88 GB (APP 40.65 MB):<br>

    Python 3.11 && Cuda 12.4 && Upgraded to torch-2.5.1+cu124-cp311-cp311-linux_x86_64 && xformers

BKOHYA 'official':<br>

    This does **NOT** exist

BKOHYA 'latest' 11.61 GB (APP 58.57 MB):<br>

    Python 3.10 && FLUX.1 version with torch-2.5.0+cu124 (setup-runpod.sh with requirements_runpod.txt)
    (kohya_ss 'sd3-flux.1' branch and sd-scripts 'SD3' branch)

Example ENV vars to 'pre-select' a specific APP version:<br>

VENV_VERSION_BCOMFY=latest<br>
VENV_VERSION_BFORGE=latest<br>
VENV_VERSION_BA1111=latest<br>
VENV_VERSION_BKOHYA=latest<br>

**NOTE**: Kohya currently is only available as the 'latest' (FLUX-)Version, and has **NO** 'official' version!<br><br>
**NOTE**: The selected VENV also controls the setup of the App,<br>
e.g. for BCOMFY 'latest', it also installs and activates 12 additional popular workflow 'custom nodes':<br>
- https://github.com/cubiq/ComfyUI_essentials
- https://github.com/rgthree/rgthree-comfy
- https://github.com/WASasquatch/was-node-suite-comfyui
- https://github.com/Fannovel16/comfyui_controlnet_aux
- https://github.com/XLabs-AI/x-flux-comfyui
- https://github.com/city96/ComfyUI-GGUF
- https://github.com/kijai/ComfyUI-Florence2
- https://github.com/kijai/ComfyUI-KJNodes
- https://github.com/ssitu/ComfyUI_UltimateSDUpscale
- https://github.com/gseth/ControlAltAI-Nodes
- https://github.com/yolain/ComfyUI-Easy-Use
- https://github.com/ltdrdata/ComfyUI-Impact-Pack

**NOTE**: If it makes sense, additional app versions will be added to the MANIFEST later, e.g. 'experimental' versions ;-)<br>

## Future plans

**We also plan for additional Apps**:<br>
- @ostris `ai-toolkit` - another popular Trainer app, see https://github.com/ostris/ai-toolkit
- @MNeMoNiCuZ `joy-caption-batch` - a popular captioning app, see https://github.com/MNeMoNiCuZ/joy-caption-batch
for captioning with https://www.aimodels.fyi/models/huggingFace/llama-joycaption-alpha-two-hf-llava-fancyfeast

Such a captioning app adds very nicely with the need to have good captions for Trainers like `kohya_ss` and `ai-toolkit`, specifically when training custom LoRA `Flux.1` models.

## Better AI-Launcher Features

All Apps can now be also `refreshed` any time - with their `'Refresh Application'` button - to the latest GitHub state of their corresponding Repos. This will include refreshing repo sub-modules (as in the case with 'kohya_ss'), and also will refresh 'custom_nodes' (in the case of 'ComfyUI's installed 12 custom nodes). In the case of 'ComfyUI' also all custom module requirements will be updated to their latest definitions.<br>
Note however, that refreshing an app needs to `reset` its status to the state, as when it was last installed/cloned!<br>
That means that any changes in the `app_path` (existing files edited or new files added) get lost, including local model downloads into the various `models` sub-folders of the app!<br>

Before refreshing, the `Refresh Symlinks` code will be called to `pull-back` any locally downloaded model files,
and save them into the `'shared_models'` workspace folder, before the actual `reset` is done.<br>
So this operation is not 'light' and you should plan for that accordingly!<br>

Every App also can be `deleted` and installed as another version with its `'Delete Application'` button.<br>
When `deleting` an app, the same logic applies as during `refreshing` and app, and the same `Refresh Symlinks` code will be called to `pull-back` any locally downloaded model files, and save them into the `'shared_models'` workspace folder, before the actual deletion of the app is done.<br>
This should make it easier to switch between app versions, if needed ;-)<br>

`Downloading` and `Unpacking` of app versions runs with the fastest available options:
- Downloads:
    ATM we use `aria2c --max-connection-per-server=16 --max-concurrent-downloads=16 --split=16` for downloading app version `TAR.gz` archives from a central `S3 bucket location`.<br>
- Unpacking:
    The `TAR.gz` archives are compressed with `'gzip -9'` option to achieve the lowest possible archive file size during download, which at the same time still provides fast Unpacking rates.<br>
    Unpacking the archives is done also as fast as possible with `PIGZ`, a parallel version of gzip. Although it only uses a single thread for decompression, it starts 3 additional threads for reading, writing, and check calculation.
- Verification:
    All downloaded TAR archives are `SHA256 hash` checked for possible download corruptions.<br>
    
    After Unpacking and after Cloning/Installing the app, both the `app_path` and also the `venv_path` of the app are checked for correct and expected folder sizes. That should help to detect corrupted installations, which - for any possible reason - did not finish their corresponding stage.<br>

This last verification part can also be done later at any time with the `'Check Application'` button of the app.<br>

If the check code detects wrong sizes for the APP or VENV folders, which are UNDER an expected minimum size of the app_path and venv_path, it offers to `delete` the app. `'Check Application'` shows a verification summary of the expected and actual APP and VENV folder sizes, and it also shows which version is currently installed and when it was last refeshed. It even shows you, when an updated app version exists online.

### Shared Models
`'Shared Models'` provides a very powerful and completely configurable `'mapping'` for all kind of 'model files, be it Checkpoints, LoRAs, Embeddings and many more, between a `'shared_models'` workspace folder, and **all** installed applications, be it the currently supported applications or **any custom app**.
The mapping is completely transparent, and can be configures with 3 different kind of `mapping JSON files`.
One map for the kinds of model types to share, another map for the installed app-path locations, and the third map `connecting` these two other maps. This allows **any** mapping to **any** app ;-)<br>

`'Shared Models'` supports file-symlinks for single-file models, but also folder-symlinks for folder-based models (e.g. most LLM models are provided as folders). The mapping supports both types of symlinks.

To further 'get started' with `'Shared Models'`, make sure to read the separate `README-SHARED-MODELS.txt` which also provides 3 sample scenarios in the form of 3 installable small TAR archives with 'test-dummy' models and a bash-script to install these test data files into your `'/workspace'` folder.
This readme file, bash-script and 3 archives can be found in the `'/app/tests'` folder within the container (or source-code):

    $ tree /app/tests
    /app/tests
    ├── README-SHARED_MODELS.txt
    ├── populate_testdata.sh
    ├── testdata_installed_apps_pull.tar.gz
    ├── testdata_shared_models_link.tar.gz
    └── testdata_stable-diffusion-webui_pull.tar.gz

    1 directory, 5 files

### Model Downloader
We also provide an intelligent `Model Downloader` to download all types of models directly into the `'shared_models'` workspace, from where these models will be automatically shared across all installed application, and mapped intelligently into their according (different named) local app model folders.<br>
This `Model Downloader` currently supports `HuggingFace` and `CivitAI` download Urls and - in the case of CivitAI - has a very smart `CivitAi Model and Version Picker Dialog`, to choose between all available 'Versions', and from any selected Version between all its available 'Files', of a specified given CivitAI Model Id Url.<br>

On the `'Models'` tab of the App-Manager, some `Example URLs` for popular Models are provided both for `HuggingFace` and for `CivitAI`.

The `Model Downloader` supports also the use of `HuggingFace` and/or `CivitAI` `security tokens`, which can be provided as `ENV vars` (see below), or stored in hidden files in the workspace, or as one-time security tokens only available in memory in the web-form during model download.<br>
This allows downloading `private models` and also `gated models` from both `HuggingFace` and `CivitAI`.

## ENV Vars (User and Secret Tokens)

**TODO: rename the file `"env.txt"` to `".env"` and adjust the ENV vars for your personal settings**
- PUBLIC_KEY=ssh-ed25519 xxx...xxx usermail@domain.com

    your `PUBLIC ssh-key`<br>
    **Note**: make sure to use the **full line content** from your `"*.pub"` key file!

- HF_TOKEN=hf_xxx...xxx

    Your `HuggingFace` token.<br><br>
    Can be a `READ` scoped token for downloading your `private` models, or `gated models` as e.g. `Flux.1 Dev` or METAs `Llama LLM models`.<br>
    The HF_TOKEN need to be a `READ/WRITE` scoped token, if you plan also to **UPLOAD** models to `HuggingFace` later, when we support direct uploads of your trained models from Trainer Apps like `kohya_ss` or later from `ai-toolkit`.

- CIVITAI_API_TOKEN=xxx...xxx

    Your `CivitAI` API token.<br><br>
    **Note**: CivitAI currently only provides a `FULL` user token, acting as `you`, so be careful with how to setup this token and with whom you share it!


**SECURITY TIP:**

These three, user-specific and **security sensitive environment vars**, should be stored as RUNPOD **`SECRETS`** and be referenced directly in your POD Template in the format `{{ RUNPOD_SECRET_MYENVVAR }}`.

From https://docs.runpod.io/pods/templates/secrets

You can reference your Secret directly in the Environment Variables section of your Pod template. To reference your Secret, reference it's key appended to the `RUNPOD_SECRET_` prefix.

That mean, for this template/image, you should use these formats to pass the above ENV vars into the docker container:

- `{{ RUNPOD_SECRET_PUBLIC_KEY}}`

- `{{ RUNPOD_SECRET_HF_TOKEN }}`

- `{{ RUNPOD_SECRET_CIVITAI_API_TOKEN }}`

(c) 2024 RunPod Better App Manager. Created by Madiator2011 & lutzapps.