export interface User {
  user_id: number
  document: string
  full_name: string
  role: string
}

export interface EventDay {
  event_day_id: number
  event_date: string
  day_label: string
}

export interface EventContext {
  event: { event_id: number; code: string; name: string }
  days: EventDay[]
  buses: { bus_id: number; bus_number: number; display_name: string }[]
  suggested_day_id: number | null
  today: string
}

export interface AttendanceSummary {
  attendance_id: number
  actual_day_id: number
  actual_date: string
  actual_day: string
  bus_id: number
  bus_number: number
  display_name: string
  checked_in_at: string
  registered_by_document: string
  registered_by_name: string
  titular_present: boolean
  actual_companions: number
  total_present: number
}

export interface Participant {
  participant_id: number
  document: string
  full_name: string
  registration_id: number
  planned_day_id: number
  planned_date: string
  planned_day: string
  planned_companion_count: number
  already_attended: boolean
  attendance: AttendanceSummary | null
}

export interface AttendanceMember {
  member_number: number
  member_type: 'TITULAR' | 'COMPANION'
  is_present: boolean
}
