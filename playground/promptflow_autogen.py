import autogen
# please ensure you have a json config file
env_or_file = "/home/shumin/PycharmProjects/Nebular/configs/OAI_COMPATIBLE_CFG.json"

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

# region Construct Agents
import os

os.environ["AUTOGEN_USE_DOCKER"] = "True"
os.environ["PF_DISABLE_TRACING"] = "True"
llm_config = {"config_list": config_list, "cache_seed": 42}
user_proxy = autogen.UserProxyAgent(
    name="User_proxy",
    system_message="A human admin.",
    code_execution_config={
        "last_n_messages": 2,
        "work_dir": "groupchat",
        "use_docker": False,
    },  # Please set use_docker=True if docker is available to run the generated code. Using docker is safer than running the generated code directly.
    human_input_mode="TERMINATE",
)
coder = autogen.AssistantAgent(
    name="Coder",
    llm_config=llm_config,
)
pm = autogen.AssistantAgent(
    name="Product_manager",
    system_message="Creative in software product ideas.",
    llm_config=llm_config,
)
groupchat = autogen.GroupChat(agents=[user_proxy, coder, pm], messages=[], max_round=12)
manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)
# endregion

# region Start chat with promptflow trace
from promptflow.tracing import start_trace

# start a trace session, and print a url for user to check trace
# traces will be collected into below collection name
start_trace(collection="autogen-groupchat")
from opentelemetry import trace
import json


tracer = trace.get_tracer("my_tracer")
# Create a root span
with tracer.start_as_current_span("autogen") as span:
    message = "Find a latest paper about gpt-4 on arxiv and find its potential applications in software."
    user_proxy.initiate_chat(
        manager,
        message=message,
        clear_history=True,
    )
    span.set_attribute("model_name", "gpt-4o")
    # recommend to store inputs and outputs as events
    span.add_event(
        "promptflow.function.inputs", {"payload": json.dumps(dict(message=message))}
    )
    span.add_event(
        "promptflow.function.output", {"payload": json.dumps([{k: v for k, v in m.items() if k != 'role'} for m in groupchat.messages])} # role doesn't matter
    )
    span.add_event(
        "promptflow.function.end", {"payload": json.dumps(user_proxy.last_message())}
    )
# type exit to terminate the chat
# endregion