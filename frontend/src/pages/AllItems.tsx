import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Image as ImageIcon,
  FileText,
  MoreHorizontal,
  Download,
  Trash2,
  ExternalLink,
} from 'lucide-react';
import { Button } from '../components/Button';
import { UploadModal } from '../components/UploadModal';
import { memoriesApi } from '../lib/api';
import { useAppStore } from '../store';
import type { Item } from '../types';

function DocThumb() {
  return (
    <div className="w-full h-full bg-[#dfe4f2] p-3 text-[#27324a]">
      <div className="h-full rounded-[3px] bg-[#f6f7fb] px-3 py-2 shadow-inner">
        <div className="text-[11px] font-bold tracking-tight">amazon.in</div>
        <div className="mt-2 h-px bg-[#b8c1d4]" />
        <div className="mt-2 grid grid-cols-2 gap-1">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <div key={index} className="h-1.5 rounded bg-[#c8cfdd]" />
          ))}
        </div>
        <div className="mt-3 space-y-1">
          {[80, 60, 72, 48].map((width) => (
            <div key={width} className="h-1 rounded bg-[#aeb8cc]" style={{ width: `${width}%` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

interface ItemCardProps {
  item: Item;
  onClick: () => void;
}

function ItemCard({ item, onClick }: ItemCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="group relative bg-[#0e172b]/80 border border-[#263657] rounded-[10px] overflow-hidden cursor-pointer transition-all duration-200 hover:border-accent/50 hover:-translate-y-1"
      onClick={onClick}
    >
      <div className="relative aspect-[1.36/1] overflow-hidden bg-[#172139]">
        {item.imageUrl ? (
          <img
            src={item.imageUrl}
            alt={item.name}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <DocThumb />
        )}

        <div className="absolute bottom-2 left-2 bg-black/60 backdrop-blur-sm rounded px-2 py-1 flex items-center gap-1">
          {item.type === 'image' ? (
            <ImageIcon className="w-4 h-4 text-white" />
          ) : (
            <FileText className="w-4 h-4 text-white" />
          )}
        </div>
      </div>

      <div className="p-3 flex justify-between items-start">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-white truncate">
            {item.name}
          </p>
          <p className="text-xs text-gray-500 mt-1">{item.date}</p>
          {item.status && (
            <p className={`mt-1 text-xs ${
              item.status === 'failed'
                ? 'text-red-400'
                : item.status === 'ready'
                  ? 'text-green-400'
                  : 'text-blue-300'
            }`}>
              {item.status === 'failed' ? 'Failed' : item.status === 'ready' ? 'Ready' : 'Processing'}
            </p>
          )}
        </div>

        <div className="relative">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setMenuOpen((open) => !open);
            }}
            className="p-1.5 text-gray-500 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
            aria-label="More options"
          >
            <MoreHorizontal className="w-5 h-5" />
          </button>

          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute right-0 bottom-full mb-2 w-40 bg-gray-900 border border-white/10 rounded-lg overflow-hidden shadow-xl z-20"
              onClick={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                className="w-full px-4 py-2 text-left text-white hover:bg-white/10 flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download
              </button>

              <button
                type="button"
                className="w-full px-4 py-2 text-left text-white hover:bg-white/10 flex items-center gap-2"
              >
                <ExternalLink className="w-4 h-4" />
                Open
              </button>

              <button
                type="button"
                className="w-full px-4 py-2 text-left text-red-400 hover:bg-red-500/20 flex items-center gap-2"
              >
                <Trash2 className="w-4 h-4" />
                Delete
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

interface ItemPreviewProps {
  item: Item;
  onClose: () => void;
}

function ItemPreview({ item, onClose }: ItemPreviewProps) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -20 }}
          className="relative max-w-4xl w-full max-h-[90vh] bg-gray-950 rounded-2xl border border-white/10 overflow-hidden flex flex-col"
          onClick={(event) => event.stopPropagation()}
        >
          {item.imageUrl ? (
            <img
              src={item.imageUrl}
              alt={item.name}
              className="w-full max-h-[60vh] object-contain"
            />
          ) : (
            <div className="aspect-video bg-gray-800 flex flex-col items-center justify-center gap-4 p-8">
              <FileText className="w-16 h-16 text-gray-500" />
              <span className="text-gray-500">PDF Document</span>
            </div>
          )}

          <div className="p-4 border-t border-white/10 flex justify-between items-start">
            <div>
              <p className="text-lg font-semibold text-white mb-1">
                {item.name}
              </p>

              <p className="text-sm text-gray-400">
                {item.type === 'document' ? 'Document' : 'Image'} · {item.date}
              </p>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-gray-400 hover:bg-white/20 hover:text-white transition-colors"
            >
              Close
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export function AllItems() {
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const { items, setItems, addItem } = useAppStore();
  const pollingIds = useRef(new Set<string>());

  const updateItem = useCallback((id: string, update: Partial<Item>) => {
    setItems(useAppStore.getState().items.map((item) =>
      item.id === id ? { ...item, ...update } : item
    ));
  }, [setItems]);

  const toItem = useCallback((memory: Record<string, unknown>, imageUrl?: string): Item => {
    const name = String(memory.original_filename ?? memory.name ?? 'Untitled memory');
    const uploadedAt = memory.uploaded_at ? new Date(String(memory.uploaded_at)) : new Date();
    const status = String(memory.processing_status ?? memory.status ?? 'uploaded');
    return {
      id: String(memory.memory_id ?? memory.id),
      name,
      type: String(memory.mime_type ?? '').startsWith('image/') ? 'image' : 'document',
      date: Number.isNaN(uploadedAt.getTime()) ? 'Just now' : uploadedAt.toLocaleDateString(),
      imageUrl,
      size: typeof memory.size_bytes === 'number' ? memory.size_bytes : undefined,
      status: ['uploaded', 'processing', 'ready', 'failed'].includes(status)
        ? status as Item['status']
        : 'uploaded',
    };
  }, []);

  const pollStatus = useCallback(async (memoryId: string) => {
    if (pollingIds.current.has(memoryId)) return;
    pollingIds.current.add(memoryId);
    try {
      while (true) {
        const status = await memoriesApi.getStatus(memoryId);
        const processingStatus = String(status.processing_status);
        updateItem(memoryId, {
          status: ['uploaded', 'processing', 'ready', 'failed'].includes(processingStatus)
            ? processingStatus as Item['status']
            : 'processing',
        });

        if (processingStatus === 'ready' || processingStatus === 'failed') {
          if (processingStatus === 'ready') {
            const { download_url: imageUrl } = await memoriesApi.getDownloadUrl(memoryId);
            updateItem(memoryId, { imageUrl });
          }
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
    } catch (error) {
      console.error(`Failed to poll memory ${memoryId}`, error);
      updateItem(memoryId, { status: 'failed' });
    } finally {
      pollingIds.current.delete(memoryId);
    }
  }, [updateItem]);

  useEffect(() => {
    let cancelled = false;
    const loadItems = async () => {
      try {
        const response = await memoriesApi.list();
        const memories = Array.isArray(response) ? response : response.memories ?? response.items ?? [];
        const loadedItems = await Promise.all((memories as Record<string, unknown>[]).map(async (memory) => {
          const item = toItem(memory);
          if (item.status === 'ready' && item.type === 'image') {
            try {
              const { download_url: imageUrl } = await memoriesApi.getDownloadUrl(item.id);
              return { ...item, imageUrl };
            } catch (error) {
              console.error(`Failed to load image URL for memory ${item.id}`, error);
            }
          }
          return item;
        }));
        if (!cancelled) {
          setItems(loadedItems);
          loadedItems
            .filter((item) => item.status !== 'ready' && item.status !== 'failed')
            .forEach((item) => void pollStatus(item.id));
        }
      } catch (error) {
        console.error('Failed to load memories', error);
      }
    };
    void loadItems();
    return () => {
      cancelled = true;
    };
  }, [pollStatus, setItems, toItem]);

  const handleUpload = useCallback(async (files: File[]) => {
    for (const file of files) {
      const localId = `upload-${file.name}-${file.lastModified}`;
      let memoryId = localId;
      addItem({
        id: localId,
        name: file.name,
        type: file.type.startsWith('image/') ? 'image' : 'document',
        date: 'Just now',
        imageUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
        size: file.size,
        status: 'processing',
      });

      try {
        const initialized = await memoriesApi.upload(file);
        const item: Item = {
          ...toItem(initialized, file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined),
          name: file.name,
          type: file.type.startsWith('image/') ? 'image' : 'document',
          date: 'Just now',
          size: file.size,
          status: 'processing',
        };
        memoryId = item.id;
        setItems(useAppStore.getState().items.map((existing) =>
          existing.id === localId ? item : existing
        ));
        await memoriesApi.uploadToS3(initialized.upload_url, file);
        void pollStatus(item.id);
      } catch (error) {
        console.error(`Failed to upload ${file.name}`, error);
        updateItem(memoryId, { status: 'failed' });
      }
    }
  }, [addItem, pollStatus, setItems, toItem, updateItem]);

  return (
    <div className="flex-1 h-full flex flex-col bg-bg overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between px-6 pb-2 pt-8 lg:px-7 flex-shrink-0">
        <div>
          <h1 className="text-3xl font-bold text-text mb-1 tracking-tight">
            All items
          </h1>

          <p className="text-[15px] text-[#9aa9c8]">
            All your images and documents in one place.
          </p>
        </div>

        <Button onClick={() => setUploadOpen(true)}>
          <Upload className="w-5 h-5 mr-2" />
          Upload
        </Button>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto px-6 pb-8 pt-7 lg:px-7">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 xl:gap-4">
          {items.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              onClick={() => setSelectedItem(item)}
            />
          ))}
        </div>
      </div>

      {/* Item preview */}
      {selectedItem && (
        <ItemPreview
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
        />
      )}

      {/* Upload modal */}
      {uploadOpen && (
        <UploadModal
          isOpen={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onFilesSelected={(files) => {
            void handleUpload(files);
            setUploadOpen(false);
          }}
        />
      )}
    </div>
  );
}