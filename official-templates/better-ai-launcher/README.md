# madiator-docker-runpod
RunPod Docker Containers for RunPod

**Better AI Launcher Container for RunPod and local develoment**

### Build Vars ###
IMAGE_BASE=madiator2011/better-launcher

IMAGE_TAG=dev

### Github: ###
https://github.com/kodxana/madiator-docker-runpod

### ENV Vars ###

These ENV vars go into the docker container to support local debugging:
see also explanantion in ".vscode/tasks.json" or "docker-compose.debug.yml"

LOCAL_DEBUG=True

    change app to localhost Urls and local Websockets (unsecured)

FLASK_ENV=development

    changed from "production" (default)

GEVENT_SUPPORT=True

    gevent monkey-patching is being used, enable gevent support in the debugger
FLASK_DEBUG=0

    "1" allows debugging in Chrome, but then VSCode debugger not works


*User ENV Vars for Production:*

### APP specific Vars ###
DISABLE_PULLBACK_MODELS=False

the default is, that app model files, which are found locally (in only one app),
get automatically "pulled-back" into the '/workspace/shared_models' folder.
From there they will be re-linked back not only to their own "pulled-back" model-type folder,
but also will be linked back into all other corresponding app model-type folders.
So the "pulled-back" model is automatically shared to all installed apps.
If you NOT want this behaviour, then set DISABLE_PULLBACK_MODELS=True

### USER specific Vars and Secrets (Tokens) - TODO: adjust this for your personal settings ###
PUBLIC_KEY=ssh-ed25519 xxx...xxx usermail@domain.com

HF_TOKEN=hf_xxx...xxx

CIVITAI_API_TOKEN=xxx.xxx


**SECURITY TIP:**

These 3 security sensitive environment vars should be stored as RUNPOD **SECRETS** and referenced directly in your POD Template in the format {{ RUNPOD_SECRET_MYENVVAR }}

From  https://docs.runpod.io/pods/templates/secrets

You can reference your Secret directly in the Environment Variables section of your Pod template. To reference your Secret, reference it's key appended to the "RUNPOD_SECRET_" prefix.

That mean, for this template/image, you should use these formats:

{{ RUNPOD_SECRET_PUBLIC_KEY}}

{{ RUNPOD_SECRET_HF_TOKEN }}

{{ RUNPOD_SECRET_CIVITAI_API_TOKEN }}


### Ports: ###
    SSH-Port
22:22/tcp

    App-Manager
7222:7222/http

    VSCode-Server
7777:7777/http

    File-Browser
8181:8181/http


### Apps: ###
    ComfyUI
3000:3000/http

    Forge (Stable-Diffiusion-WebUI-Forge)
7862:7862/http

    A1111 (Stable-Diffiusion-WebUI)
7863:7863/http

*coming soon*

    Kohya-ss
7864:7864/http