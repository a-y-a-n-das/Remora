import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  X,
  Image as ImageIcon,
  FileText,
  MoreHorizontal,
  Download,
  Trash2,
  ExternalLink,
} from 'lucide-react';
import { Button } from '../components/Button';
import { mockItems } from '../data/mockData';
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

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpload: (files: File[]) => void;
}

function UploadModal({
  isOpen,
  onClose,
  onUpload,
}: UploadModalProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState(0);
  const [state, setState] = useState<'idle' | 'uploading' | 'success'>('idle');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;

    const remainingSlots = 10 - files.length;
    const newFiles = Array.from(fileList).slice(0, remainingSlots);

    setFiles((prev) => [...prev, ...newFiles]);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = () => {
    if (files.length === 0) return;

    setState('uploading');
    setProgress(0);

    const interval = setInterval(() => {
      setProgress((currentProgress) => {
        const nextProgress = Math.min(
          currentProgress + Math.random() * 20,
          100
        );

        if (nextProgress >= 100) {
          clearInterval(interval);

          setTimeout(() => {
            onUpload(files);
            setState('success');

            setTimeout(() => {
              setState('idle');
              setFiles([]);
              setProgress(0);
              onClose();
            }, 1000);
          }, 200);

          return 100;
        }

        return nextProgress;
      });
    }, 100);
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -20 }}
          className="relative w-full max-w-2xl bg-gray-900 rounded-2xl border border-white/10 shadow-2xl overflow-hidden"
          onClick={(event) => event.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
            <h2 className="text-lg font-semibold text-white">
              Upload files
            </h2>

            <button
              type="button"
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white rounded-lg transition-colors"
              aria-label="Close upload modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf"
              className="hidden"
              onChange={(event) => {
                handleFiles(event.target.files);
                event.target.value = '';
              }}
            />

            {state === 'uploading' ? (
              <div className="py-12 text-center">
                <div className="mx-auto mb-6 w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                  <Upload className="w-8 h-8 text-blue-400 animate-pulse" />
                </div>

                <p className="text-white font-medium mb-2">
                  Uploading...
                </p>

                <div className="w-full max-w-md mx-auto h-2 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 transition-all duration-200"
                    style={{ width: `${progress}%` }}
                  />
                </div>

                <p className="text-sm text-gray-500 mt-2">
                  {Math.round(progress)}%
                </p>
              </div>
            ) : state === 'success' ? (
              <div className="py-12 text-center">
                <div className="mx-auto mb-6 w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center">
                  <Upload className="w-8 h-8 text-green-400" />
                </div>

                <p className="text-white font-medium">
                  Upload complete
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Empty state */}
                {files.length === 0 && (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full border-2 border-dashed border-white/20 rounded-2xl p-12 text-center hover:border-blue-500/50 transition-colors cursor-pointer"
                  >
                    <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-white/5 flex items-center justify-center">
                      <Upload className="w-8 h-8 text-gray-500" />
                    </div>

                    <p className="text-white font-medium mb-2">
                      Drop files here, or{' '}
                      <span className="text-blue-400 underline">
                        browse
                      </span>
                    </p>

                    <p className="text-gray-500 text-sm">
                      Images and PDFs supported · Max 10MB each
                    </p>
                  </button>
                )}

                {/* Selected files */}
                {files.length > 0 && (
                  <>
                    <div className="space-y-3">
                      {files.map((file, index) => (
                        <div
                          key={`${file.name}-${file.lastModified}-${index}`}
                          className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg border border-white/10"
                        >
                          <div className="w-12 h-12 flex-shrink-0 rounded-lg overflow-hidden bg-gray-800 border border-white/10 flex items-center justify-center">
                            {file.type.startsWith('image/') ? (
                              <img
                                src={URL.createObjectURL(file)}
                                alt=""
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <FileText className="w-6 h-6 text-gray-500" />
                            )}
                          </div>

                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-white truncate">
                              {file.name}
                            </p>

                            <p className="text-xs text-gray-500">
                              {(file.size / 1024 / 1024).toFixed(2)} MB
                            </p>
                          </div>

                          <button
                            type="button"
                            onClick={() => removeFile(index)}
                            className="p-2 text-gray-500 hover:text-red-400 transition-colors"
                            aria-label={`Remove ${file.name}`}
                          >
                            <X className="w-5 h-5" />
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* File actions */}
                    <div className="mt-4 flex justify-end gap-3">
                      <Button
                        variant="ghost"
                        onClick={() => setFiles([])}
                      >
                        Clear all
                      </Button>

                      {files.length < 10 && (
                        <Button
                          variant="ghost"
                          onClick={() => fileInputRef.current?.click()}
                        >
                          Add more
                        </Button>
                      )}

                      <Button onClick={handleUpload}>
                        Upload {files.length > 1 ? `(${files.length})` : ''}
                      </Button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export function AllItems() {
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const handleUpload = (files: File[]) => {
    console.log('Files uploaded:', files);
  };

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
          {mockItems.map((item) => (
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
          onUpload={handleUpload}
        />
      )}
    </div>
  );
}