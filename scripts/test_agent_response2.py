import sys
import json
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

class TestSchema(BaseModel):
    name: str = Field(description="Name of the person")
    age: int = Field(description="Age")

llm = ChatOpenAI(
    model="llama3.1",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    temperature=0
)

# Use empty tools array and response format
agent = create_react_agent(llm, tools=[], response_format=TestSchema)

print("Agent built. Invoking with mock test...")
try:
    result = agent.invoke({"messages": [HumanMessage(content="My name is Alice and I am 30 years old.")]})
    print("Result Keys:", result.keys())
    if "structured_response" in result:
        print("Structured Response:", result["structured_response"])
    else:
        print("Final Message:", result["messages"][-1])
except Exception as e:
    print("Error:", e)
