import { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Image as ImageIcon,
  FileText,
  CheckCircle,
  XCircle,
  Loader2,
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
        <div className="text-[11px] font-bold tracking-tight text-[#6b7ca8]">Document</div>
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

function getStageLabel(stage?: string): string {
  switch (stage) {
    case 'uploaded':
      return 'Uploaded';
    case 'ocr':
      return 'Reading document';
    case 'embedding':
      return 'Creating memory embedding';
    case 'indexing':
      return 'Indexing memory';
    case 'ready':
      return 'Ready';
    case 'failed':
      return 'Failed';
    default:
      return stage ?? '';
  }
}

function getStageIcon(stage?: string) {
  if (!stage) return null;
  if (stage === 'ready') return <CheckCircle className="w-3 h-3 text-green-400" />;
  if (stage === 'failed') return <XCircle className="w-3 h-3 text-red-400" />;
  if (stage === 'uploaded') return <Upload className="w-3 h-3 text-blue-300" />;
  return <Loader2 className="w-3 h-3 animate-spin text-blue-300" />;
}

function ItemGridSkeleton() {
  return (
    <div
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 xl:gap-4"
      aria-label="Loading items"
    >
      {Array.from({ length: 10 }, (_, index) => (
        <div
          key={index}
          className="overflow-hidden rounded-[10px] border border-[#263657] bg-[#0e172b]/80"
        >
          <div className="aspect-[1.36/1] animate-shimmer bg-[#172139]" />
          <div className="space-y-3 p-3">
            <div className="h-4 w-3/4 animate-shimmer rounded bg-[#172139]" />
            <div className="h-3 w-1/3 animate-shimmer rounded bg-[#172139]" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface ItemCardProps {
  item: Item;
  onClick: () => void;
}

function ItemCard({ item, onClick }: ItemCardProps) {

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

        {/* Status badge overlay */}
        <div className="absolute top-2 right-2 bg-black/60 backdrop-blur-sm rounded px-2 py-1 flex items-center gap-1">
          {getStageIcon(item.processingStage)}
          <span className="text-xs text-white font-medium">
            {getStageLabel(item.processingStage)}
          </span>
        </div>
      </div>

      <div className="p-3 flex flex-col gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-white truncate">
            {item.name}
          </p>
          <p className="text-xs text-gray-500 mt-1">{item.date}</p>

          {/* Single current status row */}
          <p className="mt-1 text-xs flex items-center gap-1">
            {item.status === 'ready' && (
              <>
                <CheckCircle className="w-3 h-3 text-green-400" />
                <span className="text-green-400">Ready</span>
              </>
            )}
            {item.status === 'failed' && (
              <>
                <XCircle className="w-3 h-3 text-red-400" />
                <span className="text-red-400">Failed</span>
              </>
            )}
            {item.status && item.status !== 'ready' && item.status !== 'failed' && (
              <>
                <Loader2 className="w-3 h-3 animate-spin text-blue-300" />
                <span className="text-blue-300">{getStageLabel(item.processingStage)}</span>
              </>
            )}
          </p>
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

// Module-level polling registry - persists across component mounts
const globalPollingRegistry = new Map<string, AbortController>();

function isPolling(memoryId: string): boolean {
  return globalPollingRegistry.has(memoryId);
}

function startPolling(memoryId: string, pollFn: (signal: AbortSignal) => Promise<void>): void {
  if (globalPollingRegistry.has(memoryId)) return;
  const controller = new AbortController();
  globalPollingRegistry.set(memoryId, controller);
  void pollFn(controller.signal);
}

export function AllItems() {
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const { items, mergeItems, addItem, updateItem, addInFlightMemory, removeInFlightMemory } = useAppStore();

  const toItem = useCallback((memory: Record<string, unknown>, imageUrl?: string): Item => {
    const name = String(memory.original_filename ?? memory.name ?? 'Untitled memory');
    const uploadedAt = memory.uploaded_at ? new Date(String(memory.uploaded_at)) : new Date();
    const status = String(memory.processing_status ?? memory.status ?? 'uploaded');
    const processingStage = memory.processing_stage ? String(memory.processing_stage) : undefined;
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
      processingStage: processingStage as Item['processingStage'] | undefined,
    };
  }, []);

  const pollStatus = useCallback(async (memoryId: string, signal: AbortSignal) => {
    // Define status hierarchy for backward transition prevention
    const statusOrder = ['uploaded', 'processing', 'ready', 'failed'];
    const getStatusRank = (status: string | undefined) => status ? statusOrder.indexOf(status) : -1;

    // Exponential backoff configuration
    const BASE_POLL_INTERVAL = 2000;
    const MAX_POLL_INTERVAL = 30000;
    const MAX_POLL_DURATION = 5 * 60 * 1000; // 5 minutes max
    let pollInterval = BASE_POLL_INTERVAL;
    let pollStartTime = Date.now();

    try {
      while (!signal.aborted) {
        // Check max polling duration
        if (Date.now() - pollStartTime > MAX_POLL_DURATION) {
          console.warn(`Max polling duration exceeded for memory ${memoryId}, marking as failed`);
          updateItem(memoryId, { status: 'failed', processingStage: 'failed' });
          removeInFlightMemory(memoryId);
          break;
        }

        const status = await memoriesApi.getStatus(memoryId);
        const processingStatus = String(status.processing_status);
        const processingStage = status.processing_stage ? String(status.processing_stage) : undefined;

        // Get current item to check for backward transition
        const currentItem = useAppStore.getState().items.find((item) => item.id === memoryId);
        if (currentItem) {
          const currentRank = getStatusRank(currentItem.status);
          const newRank = getStatusRank(processingStatus);
          // Only update if new status is same or forward (not backward)
          // Exception: allow failed from any state
          if (newRank < currentRank && processingStatus !== 'failed') {
            // Stale response - skip update
          } else {
            updateItem(memoryId, {
              status: ['uploaded', 'processing', 'ready', 'failed'].includes(processingStatus)
                ? processingStatus as Item['status']
                : 'processing',
              ...(processingStage ? { processingStage: processingStage as Item['processingStage'] } : {}),
            });
            // Reset backoff on successful status update
            pollInterval = BASE_POLL_INTERVAL;
          }
        } else {
          // No current item, safe to update
          updateItem(memoryId, {
            status: ['uploaded', 'processing', 'ready', 'failed'].includes(processingStatus)
              ? processingStatus as Item['status']
              : 'processing',
            ...(processingStage ? { processingStage: processingStage as Item['processingStage'] } : {}),
          });
          pollInterval = BASE_POLL_INTERVAL;
        }

        if (processingStatus === 'ready' || processingStatus === 'failed') {
          if (processingStatus === 'ready') {
            const { download_url: imageUrl } = await memoriesApi.getDownloadUrl(memoryId);
            updateItem(memoryId, { imageUrl });
          }
          removeInFlightMemory(memoryId);
          break;
        }

        // Exponential backoff with jitter
        try {
          await new Promise((resolve, reject) => {
            const timeout = setTimeout(resolve, pollInterval);
            signal.addEventListener('abort', () => {
              clearTimeout(timeout);
              reject(new Error('Aborted'));
            });
          });
        } catch {
          break;
        }

        // Increase interval for next poll (exponential backoff with cap)
        pollInterval = Math.min(pollInterval * 1.5, MAX_POLL_INTERVAL);
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        console.error(`Failed to poll memory ${memoryId}`, error);
        updateItem(memoryId, { status: 'failed', processingStage: 'failed' });
        removeInFlightMemory(memoryId);
      }
    } finally {
      globalPollingRegistry.delete(memoryId);
    }
  }, [updateItem, removeInFlightMemory]);

  // Load items on mount - merge with any existing in-flight uploads
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
              // Keep item without imageUrl - will be retried on next poll
            }
          }
          return item;
        }));
        if (!cancelled) {
          mergeItems(loadedItems);
          // Start polling for any items that are still in-flight
          loadedItems
            .filter((item) => item.status !== 'ready' && item.status !== 'failed')
            .forEach((item) => {
              if (!isPolling(item.id)) {
                startPolling(item.id, (signal) => pollStatus(item.id, signal));
              }
            });
        }
      } catch (error) {
        console.error('Failed to load memories', error);
        // Don't clear existing items on list failure - keep in-flight uploads visible
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };
    void loadItems();
    return () => {
      cancelled = true;
    };
  }, [mergeItems, pollStatus, toItem]);

  const handleUpload = useCallback(async (files: File[]) => {
    for (const file of files) {
      try {
        // Step 1: Initialize upload - get server memory_id first
        const initialized = await memoriesApi.upload(file);
        const serverMemoryId = initialized.memory_id;

        // Step 2: Create item with server memory_id as permanent identity
        const item: Item = {
          id: serverMemoryId,
          name: file.name,
          type: file.type.startsWith('image/') ? 'image' : 'document',
          date: 'Just now',
          imageUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
          size: file.size,
          status: 'processing',
          processingStage: 'uploaded',
        };
        addItem(item);
        addInFlightMemory(serverMemoryId);

        // Step 3: Upload to S3 via presigned URL
        try {
          await memoriesApi.uploadToS3(initialized.upload_url, file);
        } catch (uploadError) {
          console.error(`Failed to upload ${file.name} to S3`, uploadError);
          continue;
        }

        // Step 4: Trigger processing pipeline
        try {
          await memoriesApi.triggerProcessing(serverMemoryId);
        } catch (triggerError) {
          console.error(`Failed to trigger processing for ${file.name}`, triggerError);
          // Don't fail the upload if trigger fails - polling will eventually pick it up
        }

        // Step 5: Start status polling (persists across unmounts)
        startPolling(serverMemoryId, (signal) => pollStatus(serverMemoryId, signal));
      } catch (error) {
        console.error(`Failed to upload ${file.name}`, error);
        // Note: If upload init fails, we don't have a server memory_id yet
        // The item was never added, so nothing to clean up
      }
    }
  }, [addItem, addInFlightMemory, pollStatus]);

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
        {isLoading && items.length === 0 ? (
          <div
            className="flex min-h-[420px] flex-col items-center justify-center gap-5"
            role="status"
            aria-live="polite"
          >
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10">
              <Loader2 className="h-7 w-7 animate-spin text-blue-300" />
            </div>
            <div className="space-y-1 text-center">
              <p className="text-base font-medium text-white">Loading your items</p>
              <p className="text-sm text-[#9aa9c8]">Getting your memories ready...</p>
            </div>
            <div className="w-full max-w-5xl">
              <ItemGridSkeleton />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 xl:gap-4">
            {items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                onClick={() => setSelectedItem(item)}
              />
            ))}
          </div>
        )}
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