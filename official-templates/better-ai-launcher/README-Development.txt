For local development of this image, you can run the image with 3 options:
- Docker Compose (production or Development)
- VS Code (F5 Debugging)


PREPARE ENV variables:

Both docker-compose YML files and the VS-Code "tasks.json" configuration file
pass a ".env" file into the container, to set User-specific ENV variables.
Edit the supplied "env.txt" template file with your values, and then rename it to ".env".
The ".env" file is in the ".gitignore" file to avoid unwanted secret-sharing with GitHub!


To build and run the image with DOCKER COMPOSE:

To run in "production":
Use the command "docker compose up":
    That runs the container without debugger, but enables localhost and a workspace bind.
    It uses the default "docker-compose.yml", which should be ADJUSTED to your workspace bind location.
    This YML file binds all application ports (7222, 8181, 7777) all browsable from localhost,
    and your SSH public key will be configured and be usable!
It uses 1 docker bind mount:
- "/workspace" can be bound to any location on your local machine (ADJUST the location in the YML file)
This option uses the default entry CMD "start.sh" as defined in the "Dockerfile".

To run in "development":
Use the command "docker compose -f docker-compose.debug.yml"
    That runs the container with a python debugger (debugpy) attached, enables localhost browsing,
    and binds the workspace from a local folder of your choice.
It uses 2 docker bind mounts:
- "/app" to mirror your app into the container (supports hot-reload) and debugging against your source files
- "/workspace" can be bound to any location on your local machine (ADJUST the location in the YML file)

This second debug YML configuration is configured with the same settings that are used for
VS-Code debugging with the VS-Code Docker Extension with Run -> Debug (F5).
BUT YOU NEED TO ATTACH THE DEBUGGER YOURSELF
Use the debugpy.wait_for_client() function to block program execution until the client is attached.
See more at https://github.com/microsoft/debugpy


It is much easier to build and run the image with VS-CODE (Run -> Debug F5):

The VS-Code Docker Extension uses 2 files in the hidden folder ".vscode":
- launch.json
- tasks.json

The "tasks.json" file is the file with most configuration settings
which basically mirrors to the "docker-compose.debug.yml"

ALL these 5 mention files (env.txt, docker-compose.yml, docker-compose.debug.yml,
launch.json, tasks.json, en.txt) are heavily commented.


NOTES
Both debugging options with "docker-compose.debug.yml", or VS-Code Docker Extenstions "tasks.json"
replace the CMD entry point of the Dockerfile to "python3", instead of "start.sh" !!!

That means that the apps on port 8181 (File-Browser) and 7777 (VSCode-Server) are
NOT available during debugging, neither will your SSH public key be configured and is not usable,
as these configuration things happen in "start.sh", but they are not needed during development.

Only the NGINX server and the Flask module will be started during debugging.