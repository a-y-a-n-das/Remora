import { useState, useCallback, useRef } from 'react';
import { X, Upload, FileText } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onFilesSelected: (files: File[]) => void;
  accept?: string;
  maxFiles?: number;
  maxSize?: number;
}

export function UploadModal({
  isOpen,
  onClose,
  onFilesSelected,
  accept = 'image/*,.pdf',
  maxFiles = 10,
  maxSize = 10 * 1024 * 1024,
}: UploadModalProps) {
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;

      const newFiles: File[] = [];

      for (const file of Array.from(fileList)) {
        if (files.length + newFiles.length >= maxFiles) break;

        if (file.size > maxSize) {
          console.warn(`Skipping ${file.name}: file exceeds maximum size`);
          continue;
        }

        newFiles.push(file);
      }

      if (newFiles.length > 0) {
        setFiles((prev) => [...prev, ...newFiles]);
        onFilesSelected(newFiles);
      }
    },
    [files.length, maxFiles, maxSize, onFilesSelected]
  );

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearFiles = useCallback(() => {
    setFiles([]);
  }, []);

  const handleClose = useCallback(() => {
    setFiles([]);
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        style={{ backgroundColor: 'rgba(0, 0, 0, 0.8)' }}
        onClick={handleClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -20 }}
          className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-border/50 bg-card shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border/30 px-6 py-4">
            <h2 className="text-lg font-semibold text-text">
              Upload files
            </h2>

            <button
              type="button"
              onClick={handleClose}
              className="rounded-lg p-1.5 text-muted transition-colors hover:bg-white/5 hover:text-text"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={accept}
              className="hidden"
              onChange={(e) => {
                handleFiles(e.target.files);
                e.target.value = '';
              }}
            />

            <div className="space-y-4">
              {/* Empty state */}
              {files.length === 0 && (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full rounded-2xl border-2 border-dashed border-border/30 p-12 text-center transition-colors hover:border-accent/50"
                >
                  <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-white/5">
                    <Upload className="h-8 w-8 text-muted" />
                  </div>

                  <p className="mb-2 font-medium text-text">
                    Drop files here, or{' '}
                    <span className="text-accent underline">
                      browse
                    </span>
                  </p>

                  <p className="text-sm text-dim">
                    Images and PDFs supported · Max{' '}
                    {(maxSize / (1024 * 1024)).toFixed(0)}MB each
                  </p>
                </button>
              )}

              {/* File list */}
              {files.length > 0 && (
                <>
                  <div className="space-y-3">
                    {files.map((file, index) => (
                      <div
                        key={`${file.name}-${file.lastModified}-${index}`}
                        className="flex items-center gap-3 rounded-xl border border-border/30 bg-card/50 p-3"
                      >
                        {/* Preview */}
                        <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border/30 bg-card">
                          {file.type.startsWith('image/') ? (
                            <img
                              src={URL.createObjectURL(file)}
                              alt=""
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <FileText className="h-6 w-6 text-muted" />
                          )}
                        </div>

                        {/* File info */}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-text">
                            {file.name}
                          </p>

                          <p className="text-xs text-dim">
                            {(file.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>

                        {/* Remove */}
                        <button
                          type="button"
                          onClick={() => removeFile(index)}
                          className="rounded-lg p-1.5 text-muted transition-colors hover:text-error"
                          aria-label={`Remove ${file.name}`}
                        >
                          <X className="h-5 w-5" />
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Actions */}
                  <div className="mt-4 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={clearFiles}
                      className="rounded-lg px-4 py-2 text-sm font-medium text-muted transition-colors hover:bg-white/5 hover:text-text"
                    >
                      Clear all
                    </button>

                    {files.length < maxFiles && (
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-h"
                      >
                        Add more
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}