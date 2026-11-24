// Shapes returned by the API (mirror backend/app/schemas)

export type Role = "purchasing" | "receiving" | "vendor";

export type User = {
  id: number;
  name: string;
  email: string;
  role: Role;
  vendor_id: number | null;
  vendor_name: string | null;
  is_active: boolean;
  created_at: string;
};

export type Vendor = {
  id: number;
  name: string;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  created_at: string;
  user_count: number;
  po_count: number;
  open_po_count: number;
};

export type POStatus = "ISSUED" | "PREPARING" | "ON_THE_WAY" | "PARTIALLY_DELIVERED" | "DELIVERED" | "CANCELLED";
export type ShipmentStatus = "ON_THE_WAY" | "DELIVERED" | "DISCREPANCY" | "RESOLVED";

export type VendorRef = { id: number; name: string };

export type Page<T> = { items: T[]; total: number; page: number; pages: number };

export type POListItem = {
  id: number;
  po_number: string;
  vendor: VendorRef;
  status: POStatus;
  issue_date: string;
  required_date: string | null;
  item_count: number;
  item_summary: string;
  overdue: boolean;
  has_open_discrepancy: boolean;
  created_at: string;
  updated_at: string;
};

export type POItem = {
  id: number;
  line_no: number;
  item_name: string;
  item_code: string | null;
  quantity_ordered: number;
  unit: string;
  vendor_confirmed_name: string | null;
  vendor_confirmed_qty: number | null;
  quantity_shipped: number;
  quantity_in_transit: number;
  quantity_received: number;
  quantity_accepted: number;
  quantity_outstanding: number;
};

export type ShipmentItem = {
  po_item_id: number;
  line_no: number;
  item_name: string;
  unit: string;
  quantity_shipped: number;
};

export type Shipment = {
  id: number;
  shipment_no: string;
  is_partial: boolean;
  courier: string | null;
  tracking_number: string | null;
  expected_delivery_date: string | null;
  dispatched_at: string;
  status: ShipmentStatus;
  overdue: boolean;
  items: ShipmentItem[];
};

export type HistoryEntry = {
  id: number;
  entity_type: string;
  entity_id: number;
  old_status: string | null;
  new_status: string;
  changed_by_name: string | null;
  changed_at: string;
  note: string | null;
};

export type PODetail = {
  id: number;
  po_number: string;
  vendor: VendorRef;
  status: POStatus;
  issue_date: string;
  required_date: string | null;
  notes: string | null;
  external_ref: string | null;
  acknowledged_at: string | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
  overdue: boolean;
  has_open_discrepancy: boolean;
  locked: boolean;
  items: POItem[];
  shipments: Shipment[];
  history: HistoryEntry[];
};

export type POItemInput = {
  item_name: string;
  item_code: string | null;
  quantity_ordered: number;
  unit: string;
};
