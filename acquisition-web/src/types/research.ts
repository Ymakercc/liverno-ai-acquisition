export interface ResearchDetail {
  status: string
  company: {
    apollo_name: string | null
    domain: string | null
    match_score: number | null
    country: string | null
    industry: string | null
    employee_count: number | null
    linkedin_url: string | null
  } | null
  contacts: Array<{
    title: string | null
    has_email: boolean
    email_status: string | null
  }>
  website_research: {
    status: string
    final_url: string
    title: string
    description: string
    signals: {
      meanWellMentioned: boolean
      matchedTerms: string[]
      directFit: boolean
    }
  }
  qualification: {
    status: string
    reason: string
    reason_code: string
    customer_profile: string
    recommended_products: Array<{ name: string; reason: string }>
    risk_flags: string[]
    failure_reason: string
  }
}
