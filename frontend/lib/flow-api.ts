import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export type StepType = 'text' | 'quick_reply' | 'button_template' | 'condition' | 'end'

export interface QuickReplyOption {
  title: string
  payload: string
  next_step_id: string
}

export interface TemplateButton {
  type: 'web_url' | 'postback'
  title: string
  url?: string
  payload?: string
  next_step_id?: string
}

export interface StepCondition {
  check: 'follow_confirmed'
  onTrue: string
  onFalse: string
}

export interface FlowStep {
  id: string
  type: StepType
  message?: string
  next_step_id?: string
  quick_replies?: QuickReplyOption[]
  title?: string
  subtitle?: string
  image_url?: string
  buttons?: TemplateButton[]
  condition?: StepCondition
}

export interface Flow {
  id?: string
  name: string
  steps: FlowStep[]
  updated_at?: number
}

interface FlowsResponse {
  flows: Flow[]
}

interface FlowResponse {
  flow: Flow
}

interface SaveFlowResponse {
  status: string
  flow: Flow
}

export interface ReelFullResponse {
  media_id: string
  config: {
    trigger_keyword: string
    dm_message: string
    comment_reply: string
    comment_replies?: string[]
    active: boolean
    flow_id?: string
  }
  is_configured: boolean
  flow: Flow | null
}

export async function listFlows(): Promise<Flow[]> {
  const response = await axios.get<FlowsResponse>(`${API_URL}/api/flows`)
  return response.data.flows || []
}

export async function getFlow(flowId: string): Promise<Flow> {
  const response = await axios.get<FlowResponse>(`${API_URL}/api/flows/${flowId}`)
  return response.data.flow
}

export async function getReelFull(reelId: string): Promise<ReelFullResponse> {
  const response = await axios.get<ReelFullResponse>(`${API_URL}/api/reels/${reelId}/full`)
  return response.data
}

export async function saveFlow(flow: Flow): Promise<Flow> {
  const payload = {
    id: flow.id || undefined,
    name: flow.name,
    steps: flow.steps,
  }
  const response = await axios.post<SaveFlowResponse>(`${API_URL}/api/flows`, payload)
  return response.data.flow
}

export function getStepTypeLabel(type: StepType): string {
  switch (type) {
    case 'text':
      return 'Send Message'
    case 'quick_reply':
      return 'Quick Reply Buttons'
    case 'button_template':
      return 'Card with Buttons'
    case 'condition':
      return 'Check Follow Status'
    case 'end':
      return 'End Flow'
    default:
      return type
  }
}

export function getStepDisplayName(step: FlowStep, index: number): string {
  return `Step ${index + 1} - ${getStepTypeLabel(step.type)}`
}

export function normalizeFlowStepIds(flow: Flow): Flow {
  const steps = flow.steps || []
  const oldToNew = new Map<string, string>()
  const newSteps = steps.map((step, index) => {
    const newId = `step_${index + 1}`
    oldToNew.set(step.id, newId)
    return { ...step, id: newId }
  })

  const remapStepId = (value?: string) => {
    if (!value) return value
    return oldToNew.get(value) || value
  }

  const remapped = newSteps.map((step) => {
    const updated: FlowStep = { ...step }
    if (updated.next_step_id) {
      updated.next_step_id = remapStepId(updated.next_step_id)
    }

    if (updated.quick_replies) {
      updated.quick_replies = updated.quick_replies.map((option) => ({
        ...option,
        next_step_id: remapStepId(option.next_step_id) || '',
      }))
    }

    if (updated.buttons) {
      updated.buttons = updated.buttons.map((button) => ({
        ...button,
        next_step_id: remapStepId(button.next_step_id),
      }))
    }

    if (updated.condition) {
      updated.condition = {
        ...updated.condition,
        onTrue: remapStepId(updated.condition.onTrue) || '',
        onFalse: remapStepId(updated.condition.onFalse) || '',
      }
    }

    return updated
  })

  return {
    ...flow,
    steps: remapped,
  }
}

export function createEmptyStep(type: StepType, id?: string): FlowStep {
  const stepId = id || `step_${Date.now()}`
  switch (type) {
    case 'text':
      return { id: stepId, type, message: '', next_step_id: '' }
    case 'quick_reply':
      return {
        id: stepId,
        type,
        message: '',
        quick_replies: [{ title: '', payload: '', next_step_id: '' }],
      }
    case 'button_template':
      return {
        id: stepId,
        type,
        title: '',
        subtitle: '',
        image_url: '',
        buttons: [{ type: 'web_url', title: '', url: '' }],
      }
    case 'condition':
      return {
        id: stepId,
        type,
        condition: { check: 'follow_confirmed', onTrue: '', onFalse: '' },
      }
    case 'end':
      return { id: stepId, type }
    default:
      return { id: stepId, type: 'end' }
  }
}

export function createEmptyFlow(): Flow {
  const generatedId =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? `flow_${crypto.randomUUID().slice(0, 8)}`
      : `flow_${Date.now()}`
  return {
    id: generatedId,
    name: 'Untitled Flow',
    steps: [createEmptyStep('text', 'step_1'), createEmptyStep('end', 'step_end')],
  }
}

export function validateFlow(flow: Flow): string[] {
  const errors: string[] = []
  const idSet = new Set<string>()

  if (!flow.name.trim()) {
    errors.push('Flow name is required.')
  }
  if (!flow.steps.length) {
    errors.push('Flow must contain at least one step.')
    return errors
  }

  for (const step of flow.steps) {
    const stepId = step.id?.trim()
    if (!stepId) {
      errors.push('Each step must have an id.')
      continue
    }
    if (idSet.has(stepId)) {
      errors.push(`Duplicate step id: ${stepId}`)
    }
    idSet.add(stepId)
  }

  const existsStep = (value?: string) => !!value && idSet.has(value.trim())

  for (const step of flow.steps) {
    const stepId = step.id || '(unknown)'

    if (step.type === 'text') {
      if (!step.message?.trim()) {
        errors.push(`Text step "${stepId}" requires a message.`)
      }
      if (step.next_step_id && !existsStep(step.next_step_id)) {
        errors.push(`Text step "${stepId}" points to missing next_step_id "${step.next_step_id}".`)
      }
    }

    if (step.type === 'quick_reply') {
      if (!step.message?.trim()) {
        errors.push(`Quick reply step "${stepId}" requires a message.`)
      }
      if (!step.quick_replies?.length) {
        errors.push(`Quick reply step "${stepId}" requires at least one option.`)
      }
      step.quick_replies?.forEach((option, index) => {
        if (!option.title.trim()) {
          errors.push(`Quick reply step "${stepId}" option ${index + 1} is missing title.`)
        }
        if (!option.payload.trim()) {
          errors.push(`Quick reply step "${stepId}" option ${index + 1} is missing payload.`)
        }
        if (!option.next_step_id.trim()) {
          errors.push(`Quick reply step "${stepId}" option ${index + 1} is missing next_step_id.`)
        } else if (!existsStep(option.next_step_id)) {
          errors.push(
            `Quick reply step "${stepId}" option ${index + 1} points to missing step "${option.next_step_id}".`
          )
        }
      })
    }

    if (step.type === 'button_template') {
      if (!step.title?.trim()) {
        errors.push(`Button template step "${stepId}" requires a title.`)
      }
      if (!step.buttons?.length) {
        errors.push(`Button template step "${stepId}" requires at least one button.`)
      }
      step.buttons?.forEach((button, index) => {
        if (!button.title.trim()) {
          errors.push(`Button template step "${stepId}" button ${index + 1} is missing title.`)
        }
        if (button.type === 'web_url') {
          if (!button.url?.trim()) {
            errors.push(`Button template step "${stepId}" web_url button ${index + 1} is missing url.`)
          }
        } else {
          if (!button.payload?.trim()) {
            errors.push(`Button template step "${stepId}" postback button ${index + 1} is missing payload.`)
          }
          if (!button.next_step_id?.trim()) {
            errors.push(
              `Button template step "${stepId}" postback button ${index + 1} is missing next_step_id.`
            )
          } else if (!existsStep(button.next_step_id)) {
            errors.push(
              `Button template step "${stepId}" postback button ${index + 1} points to missing step "${button.next_step_id}".`
            )
          }
        }
      })
    }

    if (step.type === 'condition') {
      const condition = step.condition
      if (!condition || condition.check !== 'follow_confirmed') {
        errors.push(`Condition step "${stepId}" must use check "follow_confirmed".`)
        continue
      }
      if (!condition.onTrue.trim() || !existsStep(condition.onTrue)) {
        errors.push(`Condition step "${stepId}" has invalid onTrue branch "${condition.onTrue}".`)
      }
      if (!condition.onFalse.trim() || !existsStep(condition.onFalse)) {
        errors.push(`Condition step "${stepId}" has invalid onFalse branch "${condition.onFalse}".`)
      }
    }
  }

  return errors
}
