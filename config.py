import json

with open("config.json", "r") as config_file:
    config = json.loads(config_file.read())

nicks, phrases, emotes = config["nicks"], config["phrases"], config["emotes"]
modes = {int(k): v for k, v in config["modes"].items()}


def save_config():
    to_json = {
        "nicks": nicks,
        "phrases": phrases,
        "modes": {str(k): v for k, v in modes.items()},
        "emotes": emotes,
    }
    with open("config.json", "w") as config_file:
        json.dump(to_json, config_file, indent=2)
