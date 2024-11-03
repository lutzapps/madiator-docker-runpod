group "default" {
    targets = [
        "better-ai-launcher-cuda124",
        "better-ai-launcher-cuda121"
    ]
}

target "better-ai-launcher-cuda124" {
    dockerfile = "Dockerfile"
    args = {
        BASE_IMAGE = "madiator2011/better-base:cuda12.4",
    }
    contexts = {
        scripts = "../../container-template"
    }
    tags = ["madiator2011/better-launcher:dev"]
}

target "better-ai-launcher-cuda121" {
    dockerfile = "Dockerfile"
    args = {
        BASE_IMAGE = "madiator2011/better-base:cuda12.1",
    }
    contexts = {
        scripts = "../../container-template"
    }
    tags = ["madiator2011/better-launcher:dev-cuda121"]
}