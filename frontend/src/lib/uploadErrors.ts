export type ProfileValidation = {
  passed: boolean;
  profile_status: "passed" | "failed";
  score?: number;
  issues?: string[];
  messages?: string[];
  checks?: Record<string, boolean>;
};

export function parseUploadDetail(detail: unknown): {
  message: string;
  profileValidation?: ProfileValidation;
} {
  if (typeof detail === "string") {
    return { message: detail };
  }
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; profile_validation?: ProfileValidation };
    return {
      message: d.message || "Upload failed",
      profileValidation: d.profile_validation,
    };
  }
  return { message: "Upload failed" };
}
