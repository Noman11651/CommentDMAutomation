'use client'

import {
  Flow,
  FlowStep,
  StepType,
  createEmptyStep,
  getStepTypeLabel,
  normalizeFlowStepIds,
} from '@/lib/flow-api'
import StepEditor from './StepEditor'

interface FlowEditorProps {
  flow: Flow
  onChange: (flow: Flow) => void
}

export default function FlowEditor({ flow, onChange }: FlowEditorProps) {
  const updateFlow = (patch: Partial<Flow>, normalize = false) => {
    const next = { ...flow, ...patch }
    onChange(normalize ? normalizeFlowStepIds(next) : next)
  }

  const updateStep = (index: number, nextStep: FlowStep) => {
    const steps = [...flow.steps]
    steps[index] = nextStep
    updateFlow({ steps }, true)
  }

  const removeStep = (index: number) => {
    const steps = [...flow.steps]
    steps.splice(index, 1)
    updateFlow({ steps }, true)
  }

  const moveStep = (index: number, direction: -1 | 1) => {
    const target = index + direction
    if (target < 0 || target >= flow.steps.length) return
    const steps = [...flow.steps]
    const temp = steps[index]
    steps[index] = steps[target]
    steps[target] = temp
    updateFlow({ steps }, true)
  }

  const addStep = (type: StepType) => {
    updateFlow({ steps: [...flow.steps, createEmptyStep(type)] }, true)
  }

  const stepOptions = flow.steps.map((step, index) => ({
    id: step.id,
    label: `Step ${index + 1} - ${getStepTypeLabel(step.type)}`,
  }))

  const addStepCards: Array<{ type: StepType; description: string }> = [
    { type: 'text', description: 'Send a plain DM message.' },
    { type: 'quick_reply', description: 'Show tappable quick reply options.' },
    { type: 'button_template', description: 'Send card with URL/postback buttons.' },
    { type: 'condition', description: 'Branch on follow status.' },
    { type: 'end', description: 'Stop the automation flow.' },
  ]

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-1">
        <label className="text-sm text-white/80">
          Flow Name
          <input
            value={flow.name}
            onChange={(e) => updateFlow({ name: e.target.value })}
            className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
          />
        </label>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-white/70">Add Step</h3>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {addStepCards.map((item) => (
            <button
              key={item.type}
              type="button"
              onClick={() => addStep(item.type)}
              className="rounded-xl border border-white/20 bg-white/10 p-3 text-left transition hover:bg-white/20"
            >
              <p className="text-sm font-semibold text-white">{getStepTypeLabel(item.type)}</p>
              <p className="mt-1 text-xs text-white/70">{item.description}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        {flow.steps.map((step, index) => (
          <StepEditor
            key={`${step.id}-${index}`}
            step={step}
            stepOptions={stepOptions}
            index={index}
            onChange={(nextStep) => updateStep(index, nextStep)}
            onRemove={() => removeStep(index)}
            onMoveUp={() => moveStep(index, -1)}
            onMoveDown={() => moveStep(index, 1)}
            disableMoveUp={index === 0}
            disableMoveDown={index === flow.steps.length - 1}
          />
        ))}
      </div>
    </div>
  )
}
