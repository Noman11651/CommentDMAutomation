'use client'

import { useState } from 'react'
import {
  FlowStep,
  QuickReplyOption,
  StepType,
  TemplateButton,
  getStepDisplayName,
  getStepTypeLabel,
} from '@/lib/flow-api'

interface StepEditorProps {
  step: FlowStep
  stepOptions: Array<{ id: string; label: string }>
  index: number
  onChange: (step: FlowStep) => void
  onRemove: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  disableMoveUp: boolean
  disableMoveDown: boolean
}

export default function StepEditor({
  step,
  stepOptions,
  index,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
  disableMoveUp,
  disableMoveDown,
}: StepEditorProps) {
  const [collapsed, setCollapsed] = useState(false)

  const updateStep = (patch: Partial<FlowStep>) => {
    onChange({ ...step, ...patch })
  }

  const setQuickReply = (optionIndex: number, patch: Partial<QuickReplyOption>) => {
    const options = [...(step.quick_replies || [])]
    options[optionIndex] = { ...options[optionIndex], ...patch }
    updateStep({ quick_replies: options })
  }

  const addQuickReply = () => {
    updateStep({
      quick_replies: [...(step.quick_replies || []), { title: '', payload: '', next_step_id: '' }],
    })
  }

  const removeQuickReply = (optionIndex: number) => {
    const options = [...(step.quick_replies || [])]
    options.splice(optionIndex, 1)
    updateStep({ quick_replies: options })
  }

  const setTemplateButton = (buttonIndex: number, patch: Partial<TemplateButton>) => {
    const buttons = [...(step.buttons || [])]
    buttons[buttonIndex] = { ...buttons[buttonIndex], ...patch }
    updateStep({ buttons })
  }

  const addTemplateButton = () => {
    updateStep({
      buttons: [...(step.buttons || []), { type: 'web_url', title: '', url: '' }],
    })
  }

  const removeTemplateButton = (buttonIndex: number) => {
    const buttons = [...(step.buttons || [])]
    buttons.splice(buttonIndex, 1)
    updateStep({ buttons })
  }

  const handleTypeChange = (newType: StepType) => {
    const base: FlowStep = { id: step.id, type: newType }
    if (newType === 'text') {
      onChange({ ...base, message: '', next_step_id: '' })
      return
    }
    if (newType === 'quick_reply') {
      onChange({
        ...base,
        message: '',
        quick_replies: [{ title: '', payload: '', next_step_id: '' }],
      })
      return
    }
    if (newType === 'button_template') {
      onChange({
        ...base,
        title: '',
        subtitle: '',
        image_url: '',
        buttons: [{ type: 'web_url', title: '', url: '' }],
      })
      return
    }
    if (newType === 'condition') {
      onChange({
        ...base,
        condition: { check: 'follow_confirmed', onTrue: '', onFalse: '' },
      })
      return
    }
    onChange(base)
  }

  const nextStepOptions = stepOptions.filter((option) => option.id && option.id !== step.id)

  return (
    <div className="rounded-2xl border border-white/20 bg-white/5 p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-white font-semibold">{getStepDisplayName(step, index)}</h3>
          <p className="text-xs text-white/60">ID: {step.id}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setCollapsed((prev) => !prev)}
            className="px-3 py-1 text-xs rounded-lg bg-cyan-500/20 text-cyan-100"
          >
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
          <button
            type="button"
            onClick={onMoveUp}
            disabled={disableMoveUp}
            className="px-3 py-1 text-xs rounded-lg bg-white/10 text-white disabled:opacity-40"
          >
            Up
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={disableMoveDown}
            className="px-3 py-1 text-xs rounded-lg bg-white/10 text-white disabled:opacity-40"
          >
            Down
          </button>
          <button
            type="button"
            onClick={onRemove}
            className="px-3 py-1 text-xs rounded-lg bg-rose-500/30 text-rose-100"
          >
            Remove
          </button>
        </div>
      </div>

      {collapsed ? (
        <p className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-white/70">
          {getStepTypeLabel(step.type)} configuration hidden.
        </p>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-1">
            <label className="text-sm text-white/80">
              Step Type
              <select
                value={step.type}
                onChange={(e) => handleTypeChange(e.target.value as StepType)}
                className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
              >
                <option value="text">Send Message</option>
                <option value="quick_reply">Quick Reply Buttons</option>
                <option value="button_template">Card with Buttons</option>
                <option value="condition">Check Follow Status</option>
                <option value="end">End Flow</option>
              </select>
            </label>
          </div>

          {step.type === 'text' && (
            <div className="grid gap-3">
              <label className="text-sm text-white/80">
                Message
                <textarea
                  value={step.message || ''}
                  onChange={(e) => updateStep({ message: e.target.value })}
                  className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white min-h-[90px]"
                />
              </label>
              <label className="text-sm text-white/80">
                Next Step (optional)
                <select
                  value={step.next_step_id || ''}
                  onChange={(e) => updateStep({ next_step_id: e.target.value })}
                  className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                >
                  <option value="">End flow after this step</option>
                  {nextStepOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {step.type === 'quick_reply' && (
            <div className="space-y-3">
              <label className="text-sm text-white/80 block">
                Message
                <textarea
                  value={step.message || ''}
                  onChange={(e) => updateStep({ message: e.target.value })}
                  className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white min-h-[90px]"
                />
              </label>
              {(step.quick_replies || []).map((option, idx) => (
                <div key={`${step.id}-qr-${idx}`} className="rounded-xl border border-white/10 p-3 bg-black/20">
                  <div className="grid gap-2 md:grid-cols-3">
                    <input
                      value={option.title}
                      onChange={(e) => setQuickReply(idx, { title: e.target.value })}
                      className="rounded-lg bg-white/10 border border-white/20 px-2 py-2 text-white"
                      placeholder="Button label"
                    />
                    <input
                      value={option.payload}
                      onChange={(e) => setQuickReply(idx, { payload: e.target.value })}
                      className="rounded-lg bg-white/10 border border-white/20 px-2 py-2 text-white"
                      placeholder="Payload value"
                    />
                    <select
                      value={option.next_step_id}
                      onChange={(e) => setQuickReply(idx, { next_step_id: e.target.value })}
                      className="rounded-lg bg-white/10 border border-white/20 px-2 py-2 text-white"
                    >
                      <option value="">Select next step</option>
                      {nextStepOptions.map((nextOption) => (
                        <option key={nextOption.id} value={nextOption.id}>
                          {nextOption.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeQuickReply(idx)}
                    className="mt-2 text-xs text-rose-200"
                  >
                    Remove option
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={addQuickReply}
                className="px-3 py-2 rounded-lg bg-cyan-500/30 text-cyan-100 text-sm"
              >
                Add quick reply option
              </button>
            </div>
          )}

          {step.type === 'button_template' && (
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <input
                  value={step.title || ''}
                  onChange={(e) => updateStep({ title: e.target.value })}
                  className="rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                  placeholder="Card title"
                />
                <input
                  value={step.subtitle || ''}
                  onChange={(e) => updateStep({ subtitle: e.target.value })}
                  className="rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                  placeholder="Card subtitle"
                />
              </div>
              <input
                value={step.image_url || ''}
                onChange={(e) => updateStep({ image_url: e.target.value })}
                className="w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                placeholder="Image URL (optional)"
              />
              {(step.buttons || []).map((button, idx) => (
                <div
                  key={`${step.id}-btn-${idx}`}
                  className="rounded-xl border border-white/10 p-3 bg-black/20 space-y-2"
                >
                  <div className="grid gap-2 md:grid-cols-2">
                    <select
                      value={button.type}
                      onChange={(e) =>
                        setTemplateButton(idx, {
                          type: e.target.value as 'web_url' | 'postback',
                          url: e.target.value === 'web_url' ? button.url || '' : undefined,
                          payload: e.target.value === 'postback' ? button.payload || '' : undefined,
                          next_step_id:
                            e.target.value === 'postback' ? button.next_step_id || '' : undefined,
                        })
                      }
                      className="rounded-lg bg-white/10 border border-white/20 px-2 py-2 text-white"
                    >
                      <option value="web_url">Open Link</option>
                      <option value="postback">Continue Flow</option>
                    </select>
                    <input
                      value={button.title}
                      onChange={(e) => setTemplateButton(idx, { title: e.target.value })}
                      className="rounded-lg bg-white/10 border border-white/20 px-2 py-2 text-white"
                      placeholder="Button label"
                    />
                  </div>
                  {button.type === 'web_url' ? (
                    <input
                      value={button.url || ''}
                      onChange={(e) => setTemplateButton(idx, { url: e.target.value })}
                      className="w-full rounded-lg bg-white/10 border border-white/20 px-2 py-2 text-white"
                      placeholder="https://..."
                    />
                  ) : (
                    <div className="grid gap-2 md:grid-cols-2">
                      <input
                        value={button.payload || ''}
                        onChange={(e) => setTemplateButton(idx, { payload: e.target.value })}
                        className="rounded-lg bg-white/10 border border-white/20 px-2 py-2 text-white"
                        placeholder="Payload (e.g. FOLLOW_CONFIRMED)"
                      />
                      <select
                        value={button.next_step_id || ''}
                        onChange={(e) => setTemplateButton(idx, { next_step_id: e.target.value })}
                        className="rounded-lg bg-white/10 border border-white/20 px-2 py-2 text-white"
                      >
                        <option value="">Select next step</option>
                        {nextStepOptions.map((nextOption) => (
                          <option key={nextOption.id} value={nextOption.id}>
                            {nextOption.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => removeTemplateButton(idx)}
                    className="text-xs text-rose-200"
                  >
                    Remove button
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={addTemplateButton}
                className="px-3 py-2 rounded-lg bg-cyan-500/30 text-cyan-100 text-sm"
              >
                Add button
              </button>
            </div>
          )}

          {step.type === 'condition' && (
            <div className="space-y-3">
              <label className="text-sm text-white/80 block">
                Check
                <select
                  value={step.condition?.check || 'follow_confirmed'}
                  onChange={(e) =>
                    updateStep({
                      condition: {
                        check: e.target.value as 'follow_confirmed',
                        onTrue: step.condition?.onTrue || '',
                        onFalse: step.condition?.onFalse || '',
                      },
                    })
                  }
                  className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                >
                  <option value="follow_confirmed">Follow Confirmed</option>
                </select>
              </label>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="text-sm text-white/80">
                  True branch
                  <select
                    value={step.condition?.onTrue || ''}
                    onChange={(e) =>
                      updateStep({
                        condition: {
                          check: 'follow_confirmed',
                          onTrue: e.target.value,
                          onFalse: step.condition?.onFalse || '',
                        },
                      })
                    }
                    className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                  >
                    <option value="">Select step</option>
                    {nextStepOptions.map((nextOption) => (
                      <option key={nextOption.id} value={nextOption.id}>
                        {nextOption.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm text-white/80">
                  False branch
                  <select
                    value={step.condition?.onFalse || ''}
                    onChange={(e) =>
                      updateStep({
                        condition: {
                          check: 'follow_confirmed',
                          onTrue: step.condition?.onTrue || '',
                          onFalse: e.target.value,
                        },
                      })
                    }
                    className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                  >
                    <option value="">Select step</option>
                    {nextStepOptions.map((nextOption) => (
                      <option key={nextOption.id} value={nextOption.id}>
                        {nextOption.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          )}

          {step.type === 'end' && (
            <p className="text-sm text-white/70">This step ends the flow immediately.</p>
          )}
        </>
      )}
    </div>
  )
}
