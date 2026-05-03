import api from '@/services/api'
import type {
  Permission,
  RoleWithPermissions,
  UpdateRolePermissionsRequest,
} from '@/types/permission'

export const permissionsService = {
  listCatalog: () =>
    api.get<Permission[]>('/permissions').then((r) => r.data),

  listRoles: () =>
    api.get<RoleWithPermissions[]>('/roles').then((r) => r.data),

  updateRolePermissions: (roleId: string, codes: string[]) =>
    api
      .put<{ message: string }>(
        `/roles/${roleId}/permissions`,
        { permission_codes: codes } satisfies UpdateRolePermissionsRequest,
      )
      .then((r) => r.data),
}
