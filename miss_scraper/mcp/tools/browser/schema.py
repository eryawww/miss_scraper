from __future__ import annotations
from typing import Any, Dict, List, Optional, Literal, get_origin
from typing import List as TList, Optional as TOptional  # avoid shadowing
from typing import Literal as TLiteral
from pydantic import BaseModel, Field, ConfigDict, create_model

FieldType = Literal["string", "number", "integer", "boolean"]

class FieldDef(BaseModel):
    """
    Minimal per-field spec for defining structured data requirements for an LLM.

    This model defines a schema for a single field, which can be used to instruct an
    LLM to generate JSON output that conforms to a specific structure and constraints.
    """
    type: FieldType = Field(
        description="The JSON data type for this field. Must be one of 'string', 'number', 'integer', or 'boolean'. Arrays are handled as comma-separated strings."
    )
    description: Optional[str] = Field(
        default=None,
        description="A clear, natural language description of what the field represents. This guides the LLM in understanding the field's semantic meaning and expected content. For example: 'The full name of the user.'."
    )
    required: bool = Field(
        default=False,
        description="Specifies if the field must be included in the output. If true, the LLM must provide a value. If false, the LLM can omit the field if the information is not available."
    )

    enum: Optional[List[Any]] = Field(
        default=None,
        description="A list of exact, case-sensitive values that are allowed for this field. The LLM must choose one of these values. Example: ['USD', 'EUR', 'GBP'] for a currency field."
    )
    minLength: Optional[int] = Field(
        default=None,
        description="For 'string' type fields, the minimum number of characters required (inclusive)."
    )
    maxLength: Optional[int] = Field(
        default=None,
        description="For 'string' type fields, the maximum number of characters allowed (inclusive)."
    )
    minimum: Optional[float] = Field(
        default=None,
        description="For 'number' or 'integer' type fields, the minimum numerical value allowed (inclusive)."
    )
    maximum: Optional[float] = Field(
        default=None,
        description="For 'number' or 'integer' type fields, the maximum numerical value allowed (inclusive)."
    )



    model_config = ConfigDict(extra="forbid")

def _py_type_from_fielddef(fd: FieldDef):
    """Return (annotation, field_kwargs) for Pydantic based on FieldDef."""
    # Base type
    if fd.type == "string":
        base_ann = str
        fkw = {}
        if fd.minLength is not None: fkw["min_length"] = fd.minLength
        if fd.maxLength is not None: fkw["max_length"] = fd.maxLength
    elif fd.type == "number":
        base_ann = float
        fkw = {}
        if fd.minimum is not None: fkw["ge"] = fd.minimum
        if fd.maximum is not None: fkw["le"] = fd.maximum
    elif fd.type == "integer":
        base_ann = int
        fkw = {}
        if fd.minimum is not None: fkw["ge"] = int(fd.minimum)
        if fd.maximum is not None: fkw["le"] = int(fd.maximum)
    elif fd.type == "boolean":
        base_ann = bool
        fkw = {}
    else:
        raise ValueError(f"Unsupported type: {fd.type}")

    # Enum restriction (if values match the base type)
    if fd.enum:
        # permit ints for number, and reject bools for integer (since bool is subclass of int)
        def ok(v):
            if base_ann is float:
                return isinstance(v, (int, float)) and not isinstance(v, bool)
            if base_ann is int:
                return isinstance(v, int) and not isinstance(v, bool)
            return isinstance(v, base_ann)
        if all(ok(v) for v in fd.enum):
            # mypy/pyright: Literal accepts a tuple via __class_getitem__
            base_ann = TLiteral[tuple(fd.enum)]  # type: ignore[index]

    return base_ann, fkw

def make_item_model(
    fields: Dict[str, FieldDef],
    *,
    name: str = "ExtractItem",
) -> type[BaseModel]:
    """
    Build a dynamic Pydantic model for ONE extracted record.
    """
    model_fields: Dict[str, tuple[Any, Any]] = {}
    for fname, spec in fields.items():
        ann, fkw = _py_type_from_fielddef(spec)
        # Handle required vs optional fields
        default_val: Any
        if spec.required:
            default_val = Field(..., description=spec.description, **fkw)
        else:
            ann = TOptional[ann]  # Optional[ann]
            default_val = Field(None, description=spec.description, **fkw)
        model_fields[fname] = (ann, default_val)

    ItemModel = create_model(name, **model_fields)  # type: ignore[arg-type]
    return ItemModel

def make_response_model(
    fields: Dict[str, FieldDef],
    *,
    item_name: str = "ExtractItem",
    response_name: str = "ExtractContentResponse",
) -> type[BaseModel]:
    """
    Build the response schema expected by the LLM:
      { "data": [ <item>, ... ] }
    """
    ItemModel = make_item_model(fields, name=item_name)
    ResponseModel = create_model(  # type: ignore[arg-type]
        response_name,
        data=(TList[ItemModel], Field(..., description="List of extracted records")),
    )
    return ResponseModel

def format_schema_for_prompt(fields: Dict[str, FieldDef]) -> tuple[str, str]:
    """
    Format schema information for inclusion in the extraction prompt.
    Returns (schema_description, field_descriptions)
    """
    # Generate schema description as JSON-like structure
    schema_structure = {}
    for field_name, field_def in fields.items():
        schema_structure[field_name] = format_field_type(field_def)
    
    schema_description = str(schema_structure).replace("'", '"')
    
    # Generate detailed field descriptions
    field_descriptions = []
    for field_name, field_def in fields.items():
        desc_parts = [f"**{field_name}** ({field_def.type})"]
        
        if field_def.description:
            desc_parts.append(f": {field_def.description}")
        
        constraints = []
        if not field_def.required:
            constraints.append("optional")
        if field_def.enum:
            constraints.append(f"allowed values: {field_def.enum}")
        if field_def.minLength is not None:
            constraints.append(f"min length: {field_def.minLength}")
        if field_def.maxLength is not None:
            constraints.append(f"max length: {field_def.maxLength}")
        if field_def.minimum is not None:
            constraints.append(f"minimum: {field_def.minimum}")
        if field_def.maximum is not None:
            constraints.append(f"maximum: {field_def.maximum}")
        
        if constraints:
            desc_parts.append(f" [{', '.join(constraints)}]")
        
        field_descriptions.append("".join(desc_parts))
    
    return schema_description, "\n".join(field_descriptions)

def format_field_type(field_def: FieldDef) -> str:
    """Format a field type for display in schema"""
    if field_def.enum:
        return f"enum({field_def.enum})"
    else:
        return field_def.type