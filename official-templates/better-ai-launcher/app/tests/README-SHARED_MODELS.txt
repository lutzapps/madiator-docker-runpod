TESTDATA AND EXPLANATION OF MAPPING EVERYTHING YOU WANT

In the folder "/app/tests" you find the following files:

/app/tests/

    - "README-SHARED_MODELS.txt" (this file)

    - "populate_testdata.sh" (bash script to un-tar and expand all testdata into the "/workspace" folder)

    - "testdata_shared_models_link.tar.gz" (Testcase #1, read below)
    - "testdata_stable-diffusion-webui_pull.tar.gz" (Testcase #2, read below)
    - "testdata_installed_apps_pull.tar.gz" (Testcase #3, read below)


CREATE TESTDATA (once done already):

cd /workspace

# For Testcase #1 - create testdata in "shared_models" folder with dummy models for most model_types:
$ tar -czf testdata_shared_models_link.tar.gz shared_models

# For Testcase #2 - create testdata with SD-Models for A1111 to be pulled back into "shared_models" and linked back:
$ tar -czf testdata_stable-diffusion-webui_pull.tar.gz stable-diffusion-webui

# For Testcase #3 -create testdata with all possible "Apps" installed into your "/workspace"
$ tar -czf /app/tests/testdata_installed_apps_pull.tar.gz Apps


USE TESTDATA:

# BEFORE(!) you run this script, read the readme ;-)

/app/tests/populate_testdata.sh::

# use these 3 test cases and extract/merge them accordingly into your workspace, bur READ before you mess you up too much!!
tar -xzf /app/tests/testdata_shared_models_link.tar.gz /workspace
tar -xzf /app/tests/testdata_stable-diffusion-webui_pull.tar.gz /workspace
tar -xzf /app/tests/testdata_installed_apps_pull.tar.gz /workspace


Testcase #1:

When you expand "./testdata_shared_models_link.tar.gz" into the "/workspace" folder, you get:

$ tree shared_models

shared_models
├── LLM
│   └── Meta-Llama-3.1-8B
│       ├── llm-Llama-modelfile1.txt
│       ├── llm-Llama-modelfile2.txt
│       └── llm-Llama-modelfile3.txt
├── ckpt
│   ├── ckpt-model1.txt
│   └── ckpt-model2.txt
├── clip
│   └── clip-model1.txt
├── controlnet
│   └── controlnet-model1.txt
├── embeddings
│   ├── embedding-model1.txt
│   └── embedding-model2.txt
├── hypernetworks
│   └── hypernetworks-model1.txt
├── insightface
│   └── insightface-model1.txt
├── ipadapters
│   ├── ipadapter-model1.txt
│   └── xlabs
│       └── xlabs-ipadapter-model1.txt
├── loras
│   ├── flux
│   │   └── flux-lora-model1.txt
│   ├── lora-SD-model1.txt
│   ├── lora-SD-model2.txt
│   ├── lora-SD-model3.txt
│   ├── lora-SD-model4.txt
│   ├── lora-SD-model5.txt
│   ├── lora-model1.txt
│   ├── lora-model2.txt
│   └── xlabs
│       └── xlabs-lora-model1.txt
├── reactor
│   ├── faces
│   │   └── reactor-faces-model1.txt
│   └── reactor-model1.txt
├── unet
│   ├── unet-model1.txt
│   └── unet-model2.txt
├── upscale_models
│   └── esrgan-model1.txt
├── vae
│   └── vae-model1.txt
└── vae-approx
    └── vae-apporox-model1.txt

20 directories, 29 files


All these "*.txt" files "simulate" model files of a specific category (model type).
When you have this test data and you click the "Recreate Symlinks" button on the "Settings" Tab, all these models will be shared with all "installed" apps, like:

A1111:		/workspace/stable-diffusion-webui
Forge:		/workspace/stable-diffusion-webui-forge
ComfyUI:	/workspace/ComfyUI
Kohya_ss:	/workspace/Kohya_ss
CUSTOM1:	/workspace/joy-caption-batch

To "simulate" the installed app, you just need to create one or all of these folders manually, as empty folders. Maybe try it one-by-one, like you would do "in-real-life".

After there is at least ONE app installed, you can test the model sharing with the above mentioned Button "Recreate Symlinks".
All of these 29 models should be shared into all "installed" apps.

When you "add" a second app, also this new app will get all these models shared into its model folders, which can be differently named.

Some model types (e.g. UNET) have a separate model folder from Checkpoints in ComfyUI, but in A1111/Forge, these 2 model types will be merged ("flattened") in one "Stable-Diffusion" model folder. See later in the third MAP shown here.

The same goes in the other direction.
LoRA models which are "organized" in subfolders like "flux" or "slabs" in shared models folder, or in ComfyUI will again be flattened for app like A1111/Forge into the only ONE "Lora" folder.
Pay attention to the details, as the Folder is called "Lora" (no "s" and capital "L" for A111/Forge), but is called "Loras" (with ending "s" and all lower-case).

You can even map/share LLM models, which mostly come installed as a folder with many files needed for one LLM. For these models, FOLDER symlinks will be created instead or regular file symlinks which are sufficient for most model files of many model types.

Some model types, like "Embeddings" are managed differently for A1111/Forge (outside its regular model folder), which is not the case for ComfyUI. All this can be tested.

You can also test to delete a "shared model" in the "shared_models directory, and all its "symlinked" copies should be also automatically removed.


Testcase #2:

In the second testdata TAR archive, you have some SD-models which simulate the installation of the model files once for ONE app, in this test case only for A1111.
The "./testdata_stable-diffusion-webui_pull.tar.gz" is easier to handle than the one for Testcase #3, as it installs directly into the "original" App install location.

$ tree stable-diffusion-webui                 

stable-diffusion-webui
├── _add
│   ├── lora-SD-model2.txt
│   ├── lora-SD-model3.txt
│   ├── lora-SD-model4.txt
│   └── lora-SD-model5.txt
└── models
    └── Lora
        └── lora-SD-model1.txt

4 directories, 5 files


Testcase #3:

In this test case you also have other apps installed already, but the principle is the same, just a little bit more careful folder management.

The "./testdata_installed_apps_pull.tar.gz.tar.gz" extracts into an "Apps" folder.
All folders in this extracted "Apps" folder should be copied into the "/workspace" folder, to simulate an installed A1111, Forge, ComfyUI and Kohya_ss. Make sure that at the end you NOT see the extracted "Apps" folder anymore, as you only used its SUB-FOLDERS to copy/move them into "/workspace" and replace/merge existing folder.

$ tree Apps

Apps
├── ComfyUI
├── Kohya_ss
├── _add
│   ├── lora-SD-model2.txt
│   ├── lora-SD-model3.txt
│   ├── lora-SD-model4.txt
│   └── lora-SD-model5.txt
├── joy-caption-batch
├── stable-diffusion-webui
│   └── models
│       └── Lora
│           └── lora-SD-model1.txt
└── stable-diffusion-webui-forge

9 directories, 5 files


This test cases #2 and #3 start with one SD LoRA model "lora-SD-model1.txt" installed only for "stable-diffusion-webui" (A1111) in its "Lora" model folder.

Wenn you have this test data installed, and you click the "Recreate Symlinks" button of the "better-ai-laucncher" template, then this "locally" (one-app-only) installed LoRA model will be found and "pulled" back into the "shared_models/loras" folder, and "re-shared" back to the pulled location in A1111.

But it will then also be shared to all other "installed" apps, like ComfyUI, Forge. But not into Kohya, as there is no "mapping rule" defined for Kohya for LoRA models.

The only "mapping rule" for Kohya which is defined, is to get all "ckpt" (Checkpoint) model files and all UNET model files shared from the corresponding "shared_models" subfolders into its /models folder (see later in the 3rd MAP below).

In the testdata "Apps" folder you also find an "_add" folder, with 4 more SD-Models to play around with the App Sharing/Syncing framework. Put the in any local app model folder and watch what happens to them and where they the can be seen/used from other apps. You either wait a fewMinutes to let this happen automatically (every 5 Minutes), or you press the "Recreate Symlinks" button at any time to kick this off.

You can also test to see what happens, when you DELETE a model file from the shared_models sub-folders, and that all its symlinks shared to all apps will also automatically be removed, so no broken links will be left behind.

When you delete a symlink in an app model folder, only the local app "looses" the model (it is just only a link to the original shared model), so no worries here. Such locally removed symlinks however will be re-created again automatically.


BUT THAT IS ONLY THE BEGINNING.
All this logic described here is controlled via 3 (three) "MAP" dictionary JSON files, which can be found also in the "/workspace/shared_models" folder, after you click the "Create Shared Folders" button on the "Settings" Tab. They will be auto-generated, if missing, or otherwise "used-as-is" :

1.) The "SHARED_MODEL_FOLDERS" map found as "SHARED_MODEL_FOLDERS_FILE"
"/workspace/shared_models/_shared_model_folders.json":
{
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

This is the "SHARED_MODEL_FOLDERS" map for the "shared_models" sub-folders, which are used by the App Model Sharing, and this is also the dictionary which is used by the "Model Downloader" Dropdown Listbox, which can be found on the "Models" Tab of the WebUI.

The idea is to make it easy for people to download their models from "Huggingface" or "CivitAI" directly into the right model type subfolder of the "/workspace/shared_models" main folder.
This "SHARED_MODEL_FOLDERS" map also is used when you click the "Create Shared Folders" button.

NOTE: pay special attention to the examples with the "loras" folder. There is one regular model type for "loras", and 2 "grouping" model types, "loras/flux" and "loras/xlabs".
We come back to "grouping" mapping rules later, when we discuss the 3rd map.

Feel free to add/remove/edit/rename items here, alls should be re-created automatically. Just nothing from renamed folders will be deleted.

NOTE: if you change something in this map file, you need to "read" it into the App via the "Create Shared Folders" button on the "Settings" Tab of the WebUI.
If new folders are found in the map, they will be created, but nothing you have already created before will be deleted or renamed automatically, so be careful not generating two folders for the same model type, or move the models manually into the renamed folder.
IMPORTANT: Also be aware that when you add or change/rename folder names here, you need to also add or change/rename these folder names in the third "SHARED_MODEL_APP_MAP" explained below!!!


2.) The "APP_INSTALL_DIRS" map found as "APP_INSTALL_DIRS_FILE"
"/workspace/shared_models/_app_install_dirs.json":
{
    # "app_name": "app_install_dir"
    "A1111": "/workspace/stable-diffusion-webui",
    "Forge": "/workspace/stable-diffusion-webui-forge",
    "ComfyUI": "/workspace/ComfyUI",
    "Kohya_ss": "/workspace/Kohya_ss",
    "CUSTOM1": "/workspace/joy-caption-batch"
}

This is the "APP_INSTALL_DIRS" map for the app install dirs within the "/workspace", and as you see, it also supports "CUSTOM" apps to be installed and participating at the model sharing.

This dictionary is "synced" with the main apps "app_configs" dictionary, so the installation folders are the same, and this should NOT be changed. What you can change in this MAP is to add "CUSTOM" apps, like "CUSTOM1" here e.g. to re-use the Llama LLM model which is centrally installed in "shared_models" under the LLM folder to be "shared" between ComfyUI and "Joy Caption Batch" tool, which is nice to generate your "Caption" files for your LoRA Training files with "Kohya_ss" for example.


3.) The "SHARED_MODEL_APP_MAP" map found as "SHARED_MODEL_APP_MAP_FILE"
"/workspace/shared_models/_shared_model_app_map.json":
{
    "ckpt": { # "model_type" (=subdir_name of SHARED_MODELS_DIR)
        # "app_name": "app_model_folderpath" (for this "model_type", path is RELATIVE to "app_install_dir" of APP_INSTALL_DIRS map)
        "ComfyUI": "/models/checkpoints",
        "A1111": "/models/Stable-diffusion",
        "Forge": "/models/Stable-diffusion",
        "Kohya_ss": "/models" # flatten all "ckpt" / "unet" models here
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
        "Kohya_ss": "/models" # flatten all "ckpt" / "unet" models here
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

This third and last "SHARED_MODEL_APP_MAP" "connects" the "SHARED_MODEL_FOLDERS" map with the "APP_INSTALL_DIRS" map, to have a very flexible "Mapping" between all apps.

You can custom define all folder/directory layouts and namings of model types, which you can think of.

Add new mappings to your likings.
And if you don't need some of these mappings, then change them, or delete them.
This is sample data to give you a head start what you can do.

NOTE: as already introduced before, with the 3 "loras" model type folders, here we now see the 2 grouping model types "/loras/flux" and "/loras/xlabs" now applied in a "grouping" map rule.
"Grouping" of specific model.

E.g. LoRAs into separate sub-folders for LoRAs (e.g. "flux", "xlabs") for easier "filtering" in ComfyUI. Look this MAP and the testdata for LoRA samples of that feature.
It shows it for 2 LoRA sub-folders as just mentioned. These 2 "grouping" map rules also show how to "flatten" these sub-folders into only one "Lora" model folder for A1111/Forge, all of them go flat into their "Lora" folder, as these are apps, that do NOT support sub-folders per model type, and need therfore to have these "flux" and "xlabs" LoRAs "flattended" to see and consume them.

Try to add your own "grouping" map rule, or delete "grouping" map rules you not need.

Otherwise this "SHARED_MODEL_APP_MAP" should be self-explanatory, except for the last part with the FOLDER sharing syntax, as shown here and already mentioned LLM "Meta-Llama-3.1-8B", which will be used here, to show how an LLM model as "Meta-Llama-3.1-8B" can be shared between the app "ComfyUI" and a "CUSTOM1" defined app "joy-caption-batch".

FOLDER SHARING, e.g. LLM folder-based models:

_app_install.dirs.json:
{
    ...
    "Kohya_ss": "/workspace/Kohya_ss",
    "CUSTOM1": "/workspace/joy-caption-batch"
}

_shared_model_folders.json:
{
    ...
    "LLM": "LLM (aka Large-Language Model) is folder mapped (1 folder per model), append '/*' in the map",
}

To define a "folder" map rule, the "rule" must be an EXISTING shared foldername trailing with "/*",

e.g.
_shared_model_app_map.json:
{
    ...
    "LLM/Meta-Llama-3.1-8B/*": {
        "ComfyUI": "/models/LLM/Meta-Llama-3.1-8B/*",
        "CUSTOM1": "/model/*"
    }
}

This difference in the syntax with a trailing "/*" shows the shared_models Framework, that you NOT want the model files IN the folder to be shared one-by-one (which would not work anyway for a LLM model), but that you want to share the whole FOLDER, so EVERYTHING within the folder is also automatically shared.

Just append a "/*" to the MAP rule of the physical folder name "LLM/Meta-Llama-3.1-8B", and it will understand, that you want a FOLDER symlink from the folder path with the "/*" removed.
All pathes are relative to "/workspace/shared_models".

This will "trigger" a "folder" symlink to all defined target app folder mapped folders.
The target foldernames (defined with or without the trailing "/*") must be a NON-EXISTING app foldername, which will be the target folder symlink from the shared folder source.

Here are the detailes of this folder symlink for "ComfyUI":

$ cd ComfyUI/models/LLM
$ ls -la
drwxr-xr-x  3 root root  96 Oct 25 11:45 .
drwxr-xr-x 18 root root 576 Oct 25 11:45 ..
lrwxr-xr-x  1 root root  46 Oct 25 11:45 Meta-Llama-3.1-8B -> /workspace/shared_models/LLM/Meta-Llama-3.1-8B

NOTE: pay special attention to the second folder map rule for the "CUSTOM1" app "joy-cation-batch". The target mapped folder "model" has a different name from the source folder "LLM/Meta-Llama-3.1-8B/", and the 3 sample LLM model files all go directly into the linked "/model" folder.

Here are the detailes of this folder symlink for "CUSTOM1" (joy-caption-batch):

$ cd joy-caption-batch
$ ls -la
drwxr-xr-x  3 root root  96 Oct 25 11:53 .
drwxr-xr-x 10 root root 320 Oct 25 11:45 ..
lrwxr-xr-x  1 root root  46 Oct 25 11:53 model -> /workspace/shared_models/LLM/Meta-Llama-3.1-8B

$ cd model
$ ls -la
drwxr-xr-x 6 root root  192 Oct 23 10:22 .
drwxr-xr-x 5 root root  160 Oct 23 10:27 ..
-rwx------ 1 root root   51 Oct 18 11:29 llm-Llama-modelfile1.txt
-rwx------ 1 root root   51 Oct 18 11:29 llm-Llama-modelfile2.txt
-rwx------ 1 root root   51 Oct 18 11:29 llm-Llama-modelfile3.txt


Folder Sharing rules is an advanced technique, and they can only be manually added, editing the "SHARED_MODEL_APP_MAP" file for such rules, as shown above.

While all new downloaded "single" model files of a model type will be automatically shared into all app model folders, "folder models" (as typically found for LLM models), need to be added to this "SHARED_MODELS_MAP" JSON file manually to be shared, as it is shown in this example.

You could also use this folder mappings for "custom" LoRA sub-categories in ComfyUI "per folder", instead of sub-folders with separate file symlinks, but I not want to go deeper here.
You can try it, nothing bad will happen.

If you delete one of these three MAP JSON files, they will be re-generated with its shown "default" content.
But when you edit/change these 3 MAP JSON files, they will be used with your changes/addings every time you use this "/workspace" volume.


That's it for the FULL version of "shared_models" sharing between apps, and how you can easily test this before using the "real data" ;-)

Regards,
lutzapps