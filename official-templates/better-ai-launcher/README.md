# better-ai-launcher
Better AI Launcher Image for RunPod and local development.

## RunPod Better App Manager
  
Welcome to the RunPod Better App Manager!  
This image allows you to easily manage and run various AI applications on your RunPod instance.
    
### Features
- Easy installation of pre-configured AI applications.
- Start, stop, and monitor running applications.
- View application logs in real-time.
- Force kill applications if needed.
- Download Manager for **HuggingFace** and **CivitAI** with `token` support for privat and gated models.
- Shared Models Management for **Downloading and Sharing all models of all types to all installed AI applications**!
    
### Supported Applications
- Better Comfy UI
- Better Forge
- Better A1111
- more Apps coming soon (AI Trainers as `Kohya` and `ai-toolkit` are planned)
    
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

- 3000/http (ComfyUI)
- 6006/http (Tensorboard [needed by kohya_ss])
- 7862/http (Forge) aka Stable-Diffiusion-WebUI-Forge
- 7863/http (A1111) aka Stable-Diffiusion-WebUI
- 7864/http (Kohya-ss) with FLUX.1 support

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

- FLASK_DEBUG=0

    "1" allows debugging in Chrome, but then the VSCode debugger will not works.<br>
    "0" is the [default], which is the same as NOT setting this ENV var at all. 

### APP specific Vars
- DISABLE_PULLBACK_MODELS=False

    The default is, that app model files, which are found locally (in only one app), get automatically `pulled-back` into the `"/workspace/shared_models"` folder.<br>
    From there they will be re-linked back not only to their own `pulled-back` model-type folder, but also will be linked back into all other corresponding app model-type folders.<br>
    So the `pulled-back` model is automatically shared to all installed apps.

    If you **NOT** want this behaviour, then set `DISABLE_PULLBACK_MODELS=True`,<br>
    otherwise set `DISABLE_PULLBACK_MODELS=False` [default], which is the same as NOT setting this ENV var at all.

## ENV Vars (User and Secret Tokens)

**TODO: rename the file `"env.txt"` to `".env"` and adjust the ENV vars for your personal settings**
- PUBLIC_KEY=ssh-ed25519 xxx...xxx usermail@domain.com

    your `PUBLIC ssh-key`<br>
    **Note**: make sure to use the **full line content** from your `"*.pub"` key file!

- HF_TOKEN=hf_xxx...xxx

    Your `HuggingFace` token.<br><br>
    Can be a `READ` scoped token for downloading your `private` models, or `gated models` as e.g. `Flux.1 Dev` or METAs `Llama LLM models`.<br>
    The HF_TOKEN need to be a `READ/WRITE` scoped token, if you plan also to **UPLOAD** models to `HuggingFace` later, when we have Trainer Apps like `Kohya` or `ai-toolkit`.

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

(c) 2024 RunPod Better App Manager. Created by Madiator2011.