from pydantic import BaseModel, Field


class PermissionResponse(BaseModel):
    id: str
    code: str
    module: str
    label: str
    description: str | None = None

    model_config = {"from_attributes": True}


class RoleWithPermissionsResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    permissions: list[str] = []  # lista de codes


class UpdateRolePermissionsRequest(BaseModel):
    """Substitui a matriz da role pelo conjunto de codes informado."""
    permission_codes: list[str] = Field(default_factory=list)


class GenericMessage(BaseModel):
    message: str
