export type PaperUploadValidation = "valid" | "invalid";

export interface UploadSubmissionItem<TFile = File> {
  localId: string;
  file: TFile;
  validation: PaperUploadValidation;
}

export interface PaperUploadSubmission<TFile = File> {
  files: TFile[];
  primaryIndex: number | null;
}

export function buildPaperUploadSubmission<TFile>(
  items: readonly UploadSubmissionItem<TFile>[],
  primaryLocalId: string | null,
): PaperUploadSubmission<TFile> {
  const validItems = items.filter((item) => item.validation === "valid");
  const files = validItems.map((item) => item.file);
  if (primaryLocalId === null || validItems.length <= 1) {
    return { files, primaryIndex: null };
  }
  const primaryIndex = validItems.findIndex((item) => item.localId === primaryLocalId);
  return { files, primaryIndex: primaryIndex >= 0 ? primaryIndex : null };
}
