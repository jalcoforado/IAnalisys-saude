import api from '@/services/api'
import type {
  UserActionResponse,
  UserInviteRequest,
  UserListItem,
  UserUpdateRequest,
} from '@/types/user'

export const usersService = {
  list: () => api.get<UserListItem[]>('/users').then((r) => r.data),

  invite: (payload: UserInviteRequest) =>
    api.post<UserActionResponse>('/users/invite', payload).then((r) => r.data),

  update: (id: string, payload: UserUpdateRequest) =>
    api.patch<UserActionResponse>(`/users/${id}`, payload).then((r) => r.data),

  deactivate: (id: string) =>
    api.delete<UserActionResponse>(`/users/${id}`).then((r) => r.data),
}
