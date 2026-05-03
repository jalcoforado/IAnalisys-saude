export interface UserListItem {
  id: string
  email: string
  full_name: string
  is_active: boolean
  role_id: string
  role_name: string
}

export interface UserInviteRequest {
  email: string
  full_name: string
  role_id: string
}

export interface UserUpdateRequest {
  full_name?: string
  role_id?: string
  is_active?: boolean
}

export interface UserActionResponse {
  id: string
  message: string
}
