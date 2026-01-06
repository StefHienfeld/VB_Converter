/**
 * Wrapper component for the 3-card file upload section.
 */

import { FileDropZone } from "./FileDropZone";
import { ExtraInstructionInput } from "./ExtraInstructionInput";
import { cn } from "@/lib/utils";

export interface FileUploadSectionProps {
  // Policy file
  policyFile: File | null;
  onPolicyUpload: (files: File[]) => void;

  // Conditions files
  conditionsFiles: File[];
  onConditionsUpload: (files: File[]) => void;

  // Clause library files
  clauseLibraryFiles: File[];
  onClauseLibraryUpload: (files: File[]) => void;

  // Reference file (for yearly vs monthly comparison)
  referenceFile?: File | null;
  onReferenceUpload?: (files: File[]) => void;

  // Extra instruction
  extraInstruction: string;
  onExtraInstructionChange: (value: string) => void;

  // Styling
  className?: string;
  isCompact?: boolean;
}

export function FileUploadSection({
  policyFile,
  onPolicyUpload,
  conditionsFiles,
  onConditionsUpload,
  clauseLibraryFiles,
  onClauseLibraryUpload,
  referenceFile,
  onReferenceUpload,
  extraInstruction,
  onExtraInstructionChange,
  className,
  isCompact = false,
}: FileUploadSectionProps) {
  return (
    <div
      className={cn(
        "space-y-6 transition-all duration-700 ease-in-out origin-top",
        isCompact
          ? "scale-[0.6] opacity-40 grayscale pointer-events-none mb-[-180px]"
          : "scale-100 opacity-100 mb-8",
        className
      )}
    >
      {/* Upload Row - 4 cards horizontal */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <FileDropZone
          title="1. Polisbestand"
          description="Sleep Excel/CSV bestand"
          accept=".xlsx,.xls,.csv"
          onFileSelect={onPolicyUpload}
          status={policyFile ? "success" : "idle"}
          uploadedFile={
            policyFile ? { name: policyFile.name, size: policyFile.size } : null
          }
          className="animate-fade-up"
        />

        <FileDropZone
          title="2. Voorwaarden (optioneel)"
          description="Sleep PDF/TXT/DOCX"
          accept=".pdf,.txt,.docx"
          onFileSelect={onConditionsUpload}
          status={conditionsFiles.length > 0 ? "success" : "idle"}
          multiple={true}
          uploadedFiles={
            conditionsFiles.length > 0
              ? conditionsFiles.map((f) => ({ name: f.name, size: f.size }))
              : undefined
          }
          className="animate-fade-up animation-delay-100"
        />

        <FileDropZone
          title="3. Clausulebibliotheek (optioneel)"
          description="Upload bibliotheek"
          accept=".xlsx,.xls,.csv,.pdf,.docx,.doc"
          onFileSelect={onClauseLibraryUpload}
          status={clauseLibraryFiles.length > 0 ? "success" : "idle"}
          multiple={true}
          uploadedFiles={
            clauseLibraryFiles.length > 0
              ? clauseLibraryFiles.map((f) => ({ name: f.name, size: f.size }))
              : undefined
          }
          className="animate-fade-up animation-delay-150"
        />

        {onReferenceUpload && (
          <FileDropZone
            title="4. Referentie (optioneel)"
            description="Vorige VB analyse (jaar)"
            accept=".xlsx,.xls"
            onFileSelect={onReferenceUpload}
            status={referenceFile ? "success" : "idle"}
            uploadedFile={
              referenceFile ? { name: referenceFile.name, size: referenceFile.size } : null
            }
            className="animate-fade-up animation-delay-200"
          />
        )}
      </div>

      <ExtraInstructionInput
        value={extraInstruction}
        onChange={onExtraInstructionChange}
        className="animate-fade-up animation-delay-200"
      />
    </div>
  );
}
