export interface ContaAzulStatus {
  connected: boolean
  status: 'ativo' | 'expirado' | 'desconectado'
  expires_at: string | null
  connected_at: string | null
  empresa_documento: string | null
  empresa_razao_social: string | null
  empresa_nome_fantasia: string | null
  empresa_data_fundacao: string | null
  empresa_email: string | null
}
