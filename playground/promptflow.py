import autogen
# please ensure you have a json config file
env_or_file = "OAI_COMPATIBLE_CFG.json"

# filters the configs by models (you can filter by other keys as well).
config_list = autogen.config_list_from_json(
    env_or_file,
    filter_dict={
        "model": {
            "gpt-4o",
            "gpt-4o-mini",
        },
    },
)