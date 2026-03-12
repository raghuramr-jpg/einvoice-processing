import sys
import json
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from agents.ingestion_agent import _get_llm
from agents.validation_agent import _get_client

client = _get_client()

@tool
def validate_vat(vat_number: str) -> str:
    """Validate a VAT number against the ERP supplier master data."""
    return json.dumps(client.call_tool("validate_vat", {"vat_number": vat_number}))

@tool
def validate_siret(siret: str) -> str:
    """Validate a French SIRET number against the ERP supplier master data."""
    return json.dumps(client.call_tool("validate_siret", {"siret": siret}))

class ValidationDetailModel(BaseModel):
    field: str
    valid: bool
    message: str

class ValidationOutputSchema(BaseModel):
    validation_results: list[ValidationDetailModel]
    all_validations_passed: bool

tools = [validate_vat, validate_siret]
llm = _get_llm()

instruction = """You are an expert ERP Validation Agent.
You receive extracted data from an invoice. Your job is to call the necessary tools to validate the data.
Always validate VAT and SIRET.
Return the final validation results matching the ValidationOutputSchema."""

agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=instruction,
    response_format=ValidationOutputSchema,
)

print("Agent built. Invoking...")
mock_extracted = {
    "supplier_name": "TechnoVision SAS",
    "vat_number": "FR82123456789",
    "siret": "12345678901234",
}

try:
    result = agent.invoke({"messages": [HumanMessage(content=f"Please validate this invoice data: {json.dumps(mock_extracted)}")]})
    print(result.get("structured_response"))
except Exception as e:
    print("Error:", e)
