import { apiRequest } from './client'
import type { LoginRequest, RegisterRequest, TokenPairResponse, UserRead } from '../types/api'

export const authApi = {
  login: (body: LoginRequest): Promise<TokenPairResponse> =>
    apiRequest('/auth/login', { method: 'POST', body, auth: false }),

  register: (body: RegisterRequest): Promise<UserRead> =>
    apiRequest('/auth/register', { method: 'POST', body, auth: false }),

  me: (): Promise<UserRead> => apiRequest('/auth/me'),

  logout: (refreshToken: string): Promise<void> =>
    apiRequest('/auth/logout', { method: 'POST', auth: false, body: { refresh_token: refreshToken } }),
}
