export type ProcessingStage = 'uploaded' | 'ocr' | 'embedding' | 'indexing' | 'ready' | 'failed';

export interface Item {
  id: string;
  name: string;
  type: 'image' | 'document';
  date: string;
  imageUrl?: string;
  size?: number;
  status?: 'uploaded' | 'processing' | 'ready' | 'failed';
  processingStage?: ProcessingStage;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  results?: Item[];
  timestamp: Date;
}

export interface ChatSession {
  id: string;
  title: string;
  query: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

export interface SearchSession {
  id: string;
  title: string;
  query: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
}

export interface SearchResult {
  items: Item[];
  query: string;
}
