import { apiFetch, ApiError } from './client'

const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? ''

export interface MediaAsset {
  id: string
  kind: 'audio' | 'image'
  storage_path: string | null
  telegram_file_id: string | null
  mime: string | null
  created_at: string
  updated_at: string
}

export interface PresignedUrlResponse {
  url: string
  expires_in: number
}

export interface MotivationalImage {
  id: string
  media_asset_id: string
  active: boolean
}

export interface MotivationalImageCreate {
  media_asset_id: string
  active: boolean
}

export function uploadMediaAsset(
  file: File,
  kind: 'audio' | 'image',
  onProgress?: (percent: number) => void,
): Promise<MediaAsset> {
  const token = localStorage.getItem('auth_token')
  const formData = new FormData()
  formData.append('file', file)
  formData.append('kind', kind)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/api/media`)
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status === 201) {
        try {
          resolve(JSON.parse(xhr.responseText) as MediaAsset)
        } catch {
          reject(new ApiError(xhr.status, 'Invalid response'))
        }
        return
      }
      let detail: string | undefined
      try {
        const body = JSON.parse(xhr.responseText) as Record<string, unknown>
        if (typeof body.detail === 'string') detail = body.detail
      } catch {
        // ignore parse errors
      }
      reject(new ApiError(xhr.status, `Upload failed: ${xhr.status}`, detail))
    })

    xhr.addEventListener('error', () => {
      reject(new ApiError(0, 'Network error'))
    })

    xhr.addEventListener('abort', () => {
      reject(new ApiError(0, 'Upload aborted'))
    })

    xhr.send(formData)
  })
}

export function getMediaUrl(id: string): Promise<PresignedUrlResponse> {
  return apiFetch<PresignedUrlResponse>(`/api/media/${id}/url`)
}

export function listMediaAssets(kind?: 'audio' | 'image'): Promise<MediaAsset[]> {
  const query = kind ? `?kind=${kind}` : ''
  return apiFetch<MediaAsset[]>(`/api/media${query}`)
}

export function deleteMediaAsset(id: string): Promise<void> {
  return apiFetch<void>(`/api/media/${id}`, { method: 'DELETE' })
}

export function createMotivationalImage(data: MotivationalImageCreate): Promise<MotivationalImage> {
  return apiFetch<MotivationalImage>('/api/motivational-images', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
