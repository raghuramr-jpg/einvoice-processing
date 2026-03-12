import sys
import json
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

class TestSchema(BaseModel):
    name: str
    age: int

llm = ChatOpenAI(
    model="llama3.1",
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    temperature=0
)

agent = create_react_agent(llm, tools=[], response_format=TestSchema)

print("Agent built.")
