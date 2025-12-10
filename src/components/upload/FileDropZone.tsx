import { useState, useCallback } from "react";
import { Upload, FileCheck, AlertCircle, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

interface FileDropZoneProps {
  title: string;
  description: string;
  accept?: string;
  onFileSelect?: (files: File[]) => void;
  status?: "idle" | "active" | "success" | "error";
  uploadedFile?: { name: string; size: number } | null;
  uploadedFiles?: { name: string; size: number }[];
  multiple?: boolean;
  className?: string;
}

export const FileDropZone = ({
  title,
  description,
  accept = ".xlsx,.xls,.csv",
  onFileSelect,
  status = "idle",
  uploadedFile,
  uploadedFiles,
  multiple = false,
  className,
}: FileDropZoneProps) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        onFileSelect?.(multiple ? files : [files[0]]);
      }
    },
    [onFileSelect, multiple]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      if (files.length > 0) {
        onFileSelect?.(multiple ? files : [files[0]]);
      }
    },
    [onFileSelect, multiple]
  );

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const currentStatus = isDragging ? "active" : status;

  return (
    <div
      className={cn(
        "floating-card floating-card-interactive p-8",
        className
      )}
    >
      <h3 className="text-base font-semibold text-foreground mb-4">{title}</h3>

      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={cn(
          "drop-zone flex flex-col items-center justify-center p-8 min-h-[200px] cursor-pointer",
          currentStatus === "active" && "drop-zone-active",
          currentStatus === "success" && "drop-zone-success",
          currentStatus === "error" && "border-destructive bg-destructive/5"
        )}
      >
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleFileInput}
          className="hidden"
          id={`file-input-${title.replace(/\s+/g, "-")}`}
        />
        <label
          htmlFor={`file-input-${title.replace(/\s+/g, "-")}`}
          className="flex flex-col items-center cursor-pointer w-full"
        >
          {currentStatus === "success" && (uploadedFile || (uploadedFiles && uploadedFiles.length > 0)) ? (
            <>
              <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mb-4">
                <FileCheck className="w-8 h-8 text-success" />
              </div>
              {multiple && uploadedFiles && uploadedFiles.length > 0 ? (
                <div className="w-full space-y-2 max-h-[200px] overflow-y-auto">
                  <p className="text-sm font-semibold text-foreground mb-2">
                    {uploadedFiles.length} bestand{uploadedFiles.length !== 1 ? "en" : ""} geüpload
                  </p>
                  {uploadedFiles.map((file, idx) => (
                    <div key={idx} className="text-left w-full p-2 bg-muted/50 rounded-lg">
                      <p className="font-medium text-foreground text-sm truncate">{file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatFileSize(file.size)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : uploadedFile ? (
                <>
                  <p className="font-semibold text-foreground mb-1">{uploadedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatFileSize(uploadedFile.size)}
                  </p>
                </>
              ) : null}
            </>
          ) : currentStatus === "error" ? (
            <>
              <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
                <AlertCircle className="w-8 h-8 text-destructive" />
              </div>
              <p className="font-medium text-destructive">Upload mislukt</p>
              <p className="text-sm text-muted-foreground">Probeer opnieuw</p>
            </>
          ) : (
            <>
              <div
                className={cn(
                  "w-16 h-16 rounded-full flex items-center justify-center mb-4 transition-all duration-300",
                  currentStatus === "active"
                    ? "bg-secondary/20 scale-110"
                    : "bg-muted"
                )}
              >
                {currentStatus === "active" ? (
                  <Upload className="w-8 h-8 text-secondary animate-bounce" />
                ) : (
                  <FileText className="w-8 h-8 text-muted-foreground" />
                )}
              </div>
              <p className="font-medium text-foreground mb-1">
                {currentStatus === "active" ? "Laat los om te uploaden" : description}
              </p>
              <p className="text-sm text-muted-foreground">
                of klik om te bladeren
              </p>
            </>
          )}
        </label>
      </div>
    </div>
  );
};
