/**
 * DTOs mirrored 1:1 from backend Pydantic response/request schemas
 * (backend/app/schemas/*.py). This file is the single source of truth for
 * shapes on the frontend — never redefine a field shape ad hoc in a
 * component. When the backend schema changes, update here first.
 *
 * Kept framework-agnostic (no React types) so it can be shared with a
 * future React Native client, per docs/ARCHITECTURE.md.
 */

// --- enums (backend/app/models/enums.py) ------------------------------------

export type QuestionType =
  | 'SINGLE_CHOICE'
  | 'MULTI_CHOICE'
  | 'BOOLEAN'
  | 'CURRENCY'
  | 'NUMBER'
  | 'DATE'
  | 'TEXT'
  | 'DOCUMENT_UPLOAD'
  | 'INFORMATION'
  | 'REVIEW_CARD'

// --- auth (backend/app/schemas/auth.py, user.py) ----------------------------

export interface RegisterRequest {
  email: string
  password: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RefreshRequest {
  refresh_token: string
}

export interface LogoutRequest {
  refresh_token: string
}

export interface TokenPairResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserRead {
  id: string
  email: string
  created_at: string
  updated_at: string
}

// --- questionnaire (backend/app/schemas/questionnaire.py) -------------------

export interface QuestionOptionRead {
  value: string
  label: string
  order_index: number
}

export interface QuestionRead {
  id: string
  key: string
  order_index: number
  question_type: QuestionType
  prompt: string
  is_required: boolean
  options: QuestionOptionRead[]
}

export interface CurrentQuestionResponse {
  question: QuestionRead | null
  is_complete: boolean
}

/** `value`'s shape depends on the target question's `question_type` — see
 * backend/app/engines/questionnaire/validation.py; each component under
 * src/features/questionnaire/questions/ builds the shape its question type
 * needs. The backend is authoritative; this type is intentionally loose
 * (`unknown`) rather than a duplicated union of validation rules. */
export interface AnswerSubmitRequest {
  question_id: string
  value: unknown
}

export interface AnswerRead {
  id: string
  filing_session_id: string
  question_id: string
  value: unknown
  is_current: boolean
  created_at: string
}

export interface SubmitAnswerResponse {
  answer: AnswerRead
  next_question: QuestionRead | null
  is_complete: boolean
}

export interface QuestionnaireProgressRead {
  total_questions: number
  answered_questions: number
  is_complete: boolean
}

// --- documents (backend/app/schemas/document.py) ----------------------------

export type DocumentStatus = 'UPLOADED' | 'DELETED'

export interface DocumentRead {
  id: string
  original_filename: string
  content_type: string
  size_bytes: number
  status: DocumentStatus
  created_at: string
  deleted_at: string | null
}

export interface DocumentUploadResponse {
  document: DocumentRead
  is_duplicate: boolean
}

export interface DocumentListResponse {
  documents: DocumentRead[]
}

// --- extraction (backend/app/schemas/extraction.py) -------------------------

export type DocumentProcessingJobStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
export type ExtractionProviderName = 'MOCK'
export type ExtractionFailureCode = 'STORAGE_OBJECT_MISSING' | 'STORAGE_ERROR' | 'PROVIDER_ERROR' | 'UNKNOWN_ERROR'

export interface DocumentProcessingJobRead {
  id: string
  tax_document_id: string
  provider: ExtractionProviderName
  status: DocumentProcessingJobStatus
  error_code: ExtractionFailureCode | null
  /** Backend-computed from error_code only — see
   * backend/app/engines/extraction/failure_classification.py. Never a raw
   * exception message. */
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ExtractedFieldRead {
  id: string
  field_name: string
  raw_value: unknown
  confidence: number
}

export interface DocumentExtractionRead {
  id: string
  provider: ExtractionProviderName
  provider_version: string
  created_at: string
  fields: ExtractedFieldRead[]
}

// --- verification (backend/app/schemas/verification.py) ---------------------

export type VerificationAction = 'CONFIRM' | 'CORRECT'

export interface VerifyFieldRequest {
  action: VerificationAction
  /** Required for CORRECT, ignored for CONFIRM. */
  value?: unknown
}

export interface ExtractedFieldVerificationRead {
  id: string
  action: VerificationAction
  verified_value: unknown
  is_current: boolean
  created_at: string
}

/** The client-independent review listing: every extracted field, whether
 * it's even reviewable at all in this app (`is_supported` — a field with no
 * domain mapping, e.g. PAN, can never be confirmed/corrected here), and its
 * current verification, if any. This is the only "grouping" signal the
 * backend gives us — see features/review/ReviewCardQuestion.tsx. */
export interface ReviewFieldRead {
  id: string
  field_name: string
  raw_value: unknown
  confidence: number
  is_supported: boolean
  current_verification: ExtractedFieldVerificationRead | null
}

export interface SalaryIncomeRead {
  id: string
  document_extraction_id: string
  employer_name: string | null
  gross_salary: string | null
  tds_deducted: string | null
  updated_at: string
}

export interface InterestIncomeRead {
  id: string
  document_extraction_id: string
  interest_amount: string | null
  updated_at: string
}

export interface VerifyFieldResponse {
  verification: ExtractedFieldVerificationRead
  salary_income?: SalaryIncomeRead | null
  interest_income?: InterestIncomeRead | null
}

// --- supported case (backend/app/schemas/supported_case.py) -----------------

export type SupportedCaseOutcome = 'SUPPORTED' | 'REVIEW_REQUIRED' | 'NOT_SUPPORTED' | 'INCOMPLETE'

export interface SupportedCaseResultRead {
  outcome: SupportedCaseOutcome
  /** Fixed, safe reason codes only — never free text. */
  reasons: string[]
}

// --- tax calculation (backend/app/schemas/tax_calculation.py) ---------------

export type TaxRegime = 'OLD' | 'NEW'

/** All monetary fields are Decimal on the backend and are serialized as
 * JSON strings (never floats/numbers) — see backend Pydantic's default
 * Decimal encoding. Render verbatim; never parse-and-recompute. */
export interface CalculationLineItemRead {
  step_code: string
  sequence_index: number
  amount: string
  step_metadata: Record<string, unknown> | null
}

export interface TaxCalculationRead {
  id: string
  regime: TaxRegime
  calculation_engine_version: string
  gross_total_income: string
  total_deductions_applied: string
  taxable_income: string
  tax_before_rebate: string
  rebate_amount: string
  tax_after_rebate: string
  cess_amount: string
  total_tax_liability: string
  total_tds_credit: string
  net_payable: string
  created_at: string
}

export interface TaxCalculationResponse {
  calculation: TaxCalculationRead
  line_items: CalculationLineItemRead[]
}
