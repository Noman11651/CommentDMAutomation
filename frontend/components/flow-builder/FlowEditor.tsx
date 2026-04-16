'use client'

import { Flow, FlowStep, StepType, createEmptyStep } from '@/lib/flow-api'
import StepEditor from './StepEditor'

interface FlowEditorProps {
  flow: Flow
  onChange: (flow: Flow) => void
}

export default function FlowEditor({ flow, onChange }: FlowEditorProps) {
  const updateFlow = (patch: Partial<Flow>) => {
    onChange({ ...flow, ...patch })
  }

  const updateStep = (index: number, nextStep: FlowStep) => {
    const steps = [...flow.steps]
    steps[index] = nextStep
    updateFlow({ steps })
  }

  const removeStep = (index: number) => {
    const steps = [...flow.steps]
    steps.splice(index, 1)
    updateFlow({ steps })
  }

  const moveStep = (index: number, direction: -1 | 1) => {
    const target = index + direction
    if (target < 0 || target >= flow.steps.length) return
    const steps = [...flow.steps]
    const temp = steps[index]
    steps[index] = steps[target]
    steps[target] = temp
    updateFlow({ steps })
  }

  const addStep = (type: StepType) => {
    const nextOrdinal = flow.steps.length + 1
    const nextId = `step_${nextOrdinal}`
    updateFlow({ steps: [...flow.steps, createEmptyStep(type, nextId)] })
  }

  const allStepIds = flow.steps.map((step) => step.id).filter(Boolean)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-sm text-white/80">
          Flow ID
          <input
            value={flow.id || ''}
            onChange={(e) => updateFlow({ id: e.target.value })}
            className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
          />
        </label>
        <label className="text-sm text-white/80">
          Flow Name
          <input
            value={flow.name}
            onChange={(e) => updateFlow({ name: e.target.value })}
            className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
          />
        </label>
      </div>

      <div className="flex flex-wrap gap-2">
        {(['text', 'quick_reply', 'button_template', 'condition', 'end'] as StepType[]).map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => addStep(type)}
            className="rounded-lg bg-cyan-500/30 px-3 py-2 text-sm text-cyan-100"
          >
            Add {type}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        {flow.steps.map((step, index) => (
          <StepEditor
            key={`${step.id}-${index}`}
            step={step}
            allStepIds={allStepIds}
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
