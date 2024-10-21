"""
To investigate directly calling LLM with openai packages (from azure)
"""
import os
from openai import AzureOpenAI
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://azureai-codegen-prototype-aiservices2124583531.openai.azure.com/"
os.environ["AZURE_OPENAI_KEY"] = "38e502f2ca544fe08e300aeb4167de83"
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2023-03-15-preview"
)

response = client.chat.completions.create(
    # model="gpt-4-32k",  # model = "deployment_name".
    model="gpt-35-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Does Azure OpenAI support customer managed keys?"},
        {"role": "assistant", "content": "Yes, customer managed keys are supported by Azure OpenAI."},
        {"role": "user", "content": "用50字讲一个故事"}
    ]
)

print(response.choices[0].message.content)

# export AZURE_OPENAI_KEY="38e502f2ca544fe08e300aeb4167de83"
# export AZURE_OPENAI_ENDPOINT="https://azureai-codegen-prototype-aiservices2124583531.openai.azure.com/"
# gpt-4-32k
# 2023-03-15-preview


