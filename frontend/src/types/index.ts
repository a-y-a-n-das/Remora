export interface Item {
  id: string;
  name: string;
  type: 'image' | 'document';
  date: string;
  imageUrl?: string;
  size?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  results?: Item[];
  timestamp: Date;
}

export interface SearchSession {
  id: string;
  query: string;
  messages: ChatMessage[];
  createdAt: Date;
}

export interface SearchResult {
  items: Item[];
  query: string;
}

export interface UploadState {
  status: 'idle' | 'dragging' | 'uploading' | 'success' | 'error';
  progress: number;
  files: File[];
  error?: string;
}