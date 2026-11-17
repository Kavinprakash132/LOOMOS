export type LangCode = "en" | "ta";
export type SlipLangCode = "en" | "ta" | "hi";
export type UserRole = "OWNER" | "SUPERVISOR";
export type LoomType = "SHUTTLE" | "RAPIER" | "AIRJET" | "WATERJET" | "PROJECTILE";
export type LoomStatus = "OPERATIONAL" | "UNDER_MAINTENANCE" | "IDLE";
export type WageMode = "PER_METRE" | "PER_LOOM_SHIFT" | "PER_SHIFT_ATTENDANCE" | "FIXED_WEEKLY";
export type WeaverRoleType = "WEAVER" | "PIRN_WINDER" | "HELPER" | "FITTER";
export type EntryMode = "DIRECT" | "COUNTER";
export type BeamStatus = "IN_STOCK" | "RUNNING" | "COMPLETED";
export type UnloadReason = "COMPLETED" | "PARTIAL_UNLOAD" | "TRANSFER";
export type AttendanceStatus = "PRESENT" | "HALF" | "ABSENT";
export type AlertStatus = "OPEN" | "ACKNOWLEDGED" | "DISMISSED";

export interface SetupStatus {
  is_initialized: boolean;
  unit_name: string | null;
  loom_count: number;
  is_demo_mode: boolean;
  active_db_name: string;
}

export interface LoomGroupInput {
  count: number;
  prefix: string;
  start_number: number;
  loom_type: LoomType;
  make_model: string;
  rated_rpm: number;
  reed_space_in: number;
}

export interface HistoricalEbSeedRow {
  period_start: string;
  period_end: string;
  units_consumed: string;
  net_bill_paise: number;
  total_power_cut_mins: number;
  notes?: string;
}

export interface HistoricalDeliverySeedRow {
  trader_name: string;
  challan_no: string;
  delivery_date: string;
  metres: string;
  applied_rate_paise: number;
  sort_name?: string;
}

export interface SetupInitializePayload {
  owner_full_name: string;
  owner_username: string;
  owner_password: string;
  unit_name: string;
  location: string;
  default_language: LangCode;
  loom_groups: LoomGroupInput[];
  shifts_per_day: number;
  default_entry_mode: EntryMode;
  seed_mode: "CLEAN" | "SAMPLE_DEMO" | "CSV_IMPORT";
  historical_eb_bills: HistoricalEbSeedRow[];
  historical_deliveries: HistoricalDeliverySeedRow[];
}

export interface User {
  id: number;
  full_name: string;
  username: string;
  role: UserRole;
  preferred_lang: LangCode;
  is_active: boolean;
  created_at: string;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface UnitSettings {
  id: number;
  unit_name: string;
  location: string;
  default_language: LangCode;
  shifts_per_day: number;
  planned_shift_mins: number;
  shift_cutoff_hour: number;
  default_entry_mode: EntryMode;
  sanctioned_kw: string;
  active_tariff_plan_id: number | null;
  setup_completed_at: string | null;
}

export interface EbTariffSlab {
  id: number;
  min_unit: number;
  max_unit: number | null;
  rate_paise_per_unit: number;
}

export interface EbTariffPlan {
  id: number;
  name: string;
  billing_cycle_days: number;
  overhead_per_kw_paise: number;
  fixed_charge_per_kw_month_paise: number;
  electricity_tax_bps: number;
  fppca_paise_per_unit: number;
  tax_on_gross: boolean;
  effective_from: string;
  notes: string | null;
  is_deleted: boolean;
  slabs: EbTariffSlab[];
}

export interface StopReason {
  id: number;
  code: string;
  label_en: string;
  label_ta: string;
  is_power_cut: boolean;
  is_active: boolean;
}

export interface Loom {
  id: number;
  loom_number: string;
  loom_type: LoomType;
  make_model: string;
  rated_rpm: number;
  reed_space_in: number;
  status: LoomStatus;
  is_active: boolean;
}

export interface WageRule {
  id: number;
  weaver_id: number;
  wage_mode: WageMode;
  rate_paise: number;
  effective_from: string;
  effective_to: string | null;
  is_deleted: boolean;
}

export interface Weaver {
  id: number;
  full_name: string;
  full_name_ta: string | null;
  full_name_hi: string | null;
  preferred_slip_lang: SlipLangCode;
  role_type: WeaverRoleType;
  phone: string;
  is_active: boolean;
  wage_rules: WageRule[];
}

export interface Trader {
  id: number;
  company_name: string;
  contact_name: string;
  phone: string;
  is_active: boolean;
}

export interface FabricSort {
  id: number;
  sort_name: string;
  warp_count: string;
  weft_count: string;
  reed: number;
  pick: number;
  width_in: string;
  agreed_rate_paise: number;
  expected_weft_kg_per_100m: string;
  wastage_pct: string;
  is_active: boolean;
}

export interface AuditLogEntry {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  changed_by: number | null;
  changed_at: string;
  old_values_json: string | null;
  new_values_json: string | null;
  reason: string | null;
}

export interface Beam {
  id: number;
  beam_no: string;
  trader_id: number;
  trader_name: string;
  sort_id: number;
  sort_name: string;
  received_date: string;
  warp_length_m: string;
  opening_woven_m: string;
  expected_tail_waste_m: string;
  returned_weft_kg: string;
  actual_waste_m: string | null;
  due_date: string | null;
  expected_pieces: number | null;
  status: BeamStatus;
  active_loom_id: number | null;
  active_loom_number: string | null;
  woven_m: string;
  usable_total_m: string;
  remaining_m: string;
  progress_pct: number;
  weft_received_kg: string;
  weft_consumed_kg: string;
  expected_weft_kg: string;
  actual_wastage_pct: number | null;
  allowed_wastage_pct: number;
  wastage_flagged: boolean;
}

export interface WeftReceipt {
  id: number;
  beam_id: number | null;
  trader_id: number | null;
  sort_id: number | null;
  received_date: string;
  bags: number;
  net_weight_kg: string;
  note: string | null;
  is_deleted: boolean;
}

export interface ShiftEntry {
  id: number;
  client_uuid: string;
  loom_id: number;
  loom_number: string | null;
  weaver_id: number;
  weaver_name: string | null;
  beam_id: number | null;
  beam_no: string | null;
  entry_date: string;
  shift_no: number;
  entry_mode: EntryMode;
  start_meter: string | null;
  end_meter: string | null;
  net_metres: string;
  planned_mins: number;
  power_cut_mins: number;
  downtime_mins: number;
  defective_metres: string;
  stop_reason_id: number | null;
  notes: string | null;
  is_deleted: boolean;
}

export interface LoomPrefillRow {
  loom_id: number;
  loom_number: string;
  loom_type: string;
  rated_rpm: number;
  default_weaver_id: number | null;
  active_beam_id: number | null;
  active_beam_no: string | null;
  active_sort_name: string | null;
  remaining_beam_m: string | null;
  last_end_meter: string | null;
  existing_entries: ShiftEntry[];
}

export interface ShiftPrefillResponse {
  suggested_date: string;
  suggested_shift: number;
  entry_date: string;
  shift_no: number;
  shifts_per_day?: number;
  planned_shift_mins: number;
  default_entry_mode: EntryMode;
  looms: LoomPrefillRow[];
}

export interface AttendanceRecord {
  id: number;
  weaver_id: number;
  weaver_name: string | null;
  attendance_date: string;
  shift_no: number;
  status: AttendanceStatus;
  note: string | null;
  is_deleted: boolean;
}

export interface CalendarDay {
  id: number;
  calendar_date: string;
  is_working_day: boolean;
  planned_shifts: number;
  note: string | null;
}

export interface AdvanceRecord {
  id: number;
  weaver_id: number;
  weaver_name: string | null;
  advance_date: string;
  amount_paise: number;
  note: string | null;
  is_deleted: boolean;
}

export interface PayslipLinePreview {
  weaver_id: number;
  weaver_name: string;
  full_name_ta: string | null;
  full_name_hi: string | null;
  preferred_slip_lang: SlipLangCode;
  role_type: WeaverRoleType;
  wage_mode: WageMode;
  units_worked: string;
  rate_paise: number;
  gross_paise: number;
  advance_deducted_paise: number;
  defect_deduction_paise: number;
  net_payable_paise: number;
  rule_breakdown: { wage_mode: string; rate_paise: number; units: string; gross_paise: number }[];
}

export interface PayslipRecord {
  id: number;
  weaver_id: number;
  weaver_name: string | null;
  preferred_slip_lang: SlipLangCode;
  period_start: string;
  period_end: string;
  wage_mode_snapshot: WageMode;
  units_worked: string;
  rate_paise_snapshot: number;
  gross_paise: number;
  advance_deducted_paise: number;
  defect_deduction_paise: number;
  net_payable_paise: number;
  status: string;
  is_deleted: boolean;
}

export interface PrintablePayslip {
  payslip: PayslipRecord;
  unit_name: string;
  unit_location: string;
  lang: SlipLangCode;
  localized_weaver_name: string;
  role_type: WeaverRoleType;
  labels: Record<string, string>;
  printed_on: string;
}

export interface DeliveryItem {
  id: number;
  beam_id: number | null;
  sort_id: number | null;
  sort_name: string | null;
  agreed_rate_paise: number | null;
  pieces: number;
  metres: string;
  applied_rate_paise: number;
  underpayment_paise: number;
  production_start_date: string | null;
  production_end_date: string | null;
  is_opening_stock: boolean;
}

export interface DeliveryRecord {
  id: number;
  trader_id: number;
  trader_name: string | null;
  challan_no: string;
  delivery_date: string;
  total_metres: string;
  source: string;
  is_deleted: boolean;
  total_amount_paise: number;
  total_underpayment_paise: number;
  has_rate_cut: boolean;
  items: DeliveryItem[];
}

export interface TraderPaymentRecord {
  id: number;
  trader_id: number;
  trader_name: string | null;
  payment_date: string;
  amount_paise: number;
  shortage_deduction_paise: number;
  reference: string | null;
  is_deleted: boolean;
}

export interface TraderLedgerSummary {
  trader_id: number;
  company_name: string;
  total_metres: string;
  billed_paise: number;
  received_paise: number;
  shortage_paise: number;
  balance_paise: number;
  underpayment_paise: number;
}

export interface ExpenseRecord {
  id: number;
  expense_date: string;
  category: string;
  amount_paise: number;
  note: string | null;
  is_deleted: boolean;
}

export interface EbReadingRecord {
  id: number;
  reading_date: string;
  kwh_total: string;
  note: string | null;
  is_deleted: boolean;
}

export interface EbBillRecord {
  id: number;
  tariff_plan_id: number | null;
  period_start: string;
  period_end: string;
  units_consumed: string;
  energy_paise: number;
  fixed_paise: number;
  tax_paise: number;
  fppca_paise: number;
  subsidy_paise: number;
  other_charges_paise: number;
  overhead_paise: number;
  net_bill_paise: number;
  total_power_cut_mins: number;
  notes: string | null;
  is_deleted: boolean;
}

export interface AlertItem {
  id: number;
  alert_type: string;
  loom_id: number | null;
  severity: string;
  message: string;
  status: AlertStatus;
  created_at: string;
}

export interface LoomOeeRow {
  loom_id: number;
  loom_number: string;
  loom_type: string;
  rated_rpm: number;
  sort_name: string | null;
  shifts_logged: number;
  net_metres: string;
  ideal_metres: string | null;
  planned_mins: number;
  operating_mins: number;
  power_cut_mins: number;
  downtime_mins: number;
  confirmed_defective_metres: string;
  availability_pct: number | null;
  performance_pct: number | null;
  utilization_ap_pct: number | null;
  quality_pct: number | null;
  full_oee_pct: number | null;
}

export interface FloorDashboard {
  period_start: string;
  period_end: string;
  today_date: string;
  today_metres: string;
  period_metres: string;
  active_looms_count: number;
  operational_looms_count: number;
  running_beams_count: number;
  weft_wastage_alerts_count: number;
  total_planned_mins: number;
  total_operating_mins: number;
  total_power_cut_mins: number;
  total_downtime_mins: number;
  total_ideal_metres: string;
  confirmed_defective_metres: string;
  availability_pct: number | null;
  performance_pct: number | null;
  utilization_ap_pct: number | null;
  quality_recorded: boolean;
  quality_pct: number | null;
  full_oee_pct: number | null;
  oee_note: string;
  open_alerts: AlertItem[];
  loom_breakdown: LoomOeeRow[];
}

export interface OwnerFinancialSummary {
  billed_revenue_paise: number;
  finalized_wages_paise: number;
  eb_bills_paise: number;
  expenses_paise: number;
  net_operating_paise: number;
  total_receivable_paise: number;
  total_rate_underpayment_paise: number;
}

export interface OwnerDashboard extends FloorDashboard {
  financials: OwnerFinancialSummary;
}

export interface ModelComparisonEntry {
  name: string;
  arch: string;
  threshold: number;
  defect_recall: number;
  defect_f1: number;
  defect_precision: number;
  macro_f1: number;
  roc_auc: number;
  overall_accuracy_pct: number;
  inference_ms: number;
  train_seconds: number;
  confusion_matrix: number[][];
}

export interface HeldOutSplitSummary {
  train_strips: number;
  val_strips: number;
  test_strips: number;
  train_defect_strips: number;
  train_clean_strips: number;
  val_defect_strips: number;
  val_clean_strips: number;
  test_defect_strips: number;
  test_clean_strips: number;
  test_total_patches: number;
  test_defect_patches: number;
  test_clean_patches: number;
  imbalance_note: string;
}

export interface ReferenceSampleInfo {
  id: string;
  title: string;
  defect_code: string;
  ground_truth_label: string;
  is_defect: boolean;
  filename: string;
  image_url: string;
}

export interface ModelCardResponse {
  winning_model_name: string;
  model_version: string;
  architecture: string;
  threshold: number;
  held_out_split_summary: HeldOutSplitSummary;
  comparison: ModelComparisonEntry[];
  samples: ReferenceSampleInfo[];
}

export interface DefectPredictionInfo {
  model_version: string;
  predicted_label: string;
  confidence: number;
  threshold_used: number;
  is_uncertain: boolean;
  inference_ms: number;
}

export interface InspectionRecord {
  id: number;
  loom_id: number | null;
  loom_number: string | null;
  beam_id: number | null;
  beam_no: string | null;
  weaver_id: number | null;
  weaver_name: string | null;
  shift_entry_id: number | null;
  raw_image_url: string;
  heatmap_image_url: string | null;
  review_status: "PENDING" | "CONFIRMED_DEFECT" | "CONFIRMED_CLEAN";
  reviewed_label: string | null;
  defective_metres: string;
  is_reference_sample: boolean;
  inspected_at: string;
  prediction: DefectPredictionInfo | null;
}
