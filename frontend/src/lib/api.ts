import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('remora_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const memoriesApi = {
  list: async () => {
    const response = await api.get('/memories');
    return response.data;
  },

  upload: async (file: File) => {
    const response = await api.post('/memories/upload', {
      filename: file.name,
      mime_type: file.type,
      size_bytes: file.size,
    });
    return response.data;
  },

  uploadToS3: async (url: string, file: File) => {
    await axios.put(url, file, {
      headers: { 'Content-Type': file.type },
    });
  },

  getStatus: async (memoryId: string) => {
    const response = await api.get(`/memories/${memoryId}/status`);
    return response.data;
  },

  getDownloadUrl: async (memoryId: string) => {
    const response = await api.get(`/memories/${memoryId}/download-url`);
    return response.data;
  },

  search: async (query: string, limit = 10) => {
    const response = await api.post('/memories/query', { query, limit });
    return response.data;
  },
};

export const healthApi = {
  check: async () => {
    const response = await api.get('/health');
    return response.data;
  },
};

export const setAuthToken = (token: string | null) => {
  if (token) {
    localStorage.setItem('remora_token', token);
  } else {
    localStorage.removeItem('remora_token');
  }
};