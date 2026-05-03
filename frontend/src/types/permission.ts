export interface Permission {
  id: string
  code: string
  module: string
  label: string
  description: string | null
}

export interface RoleWithPermissions {
  id: string
  name: string
  description: string | null
  permissions: string[]
}

export interface UpdateRolePermissionsRequest {
  permission_codes: string[]
}
