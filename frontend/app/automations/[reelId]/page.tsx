'use client'

import { useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import axios from 'axios'
import FlowEditor from '@/components/flow-builder/FlowEditor'
import {
  Flow,
  FlowStep,
  createEmptyFlow,
  getReelFull,
  getStepTypeLabel,
  saveFlow,
  validateFlow,
} from '@/lib/flow-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ReelConfig {
  trigger_keyword: string
  dm_message: string
  comment_reply: string
  active: boolean
  flow_id?: string
}

export default function ReelAutomationFlowPage() {
  const params = useParams<{ reelId: string }>()
  const router = useRouter()
  const reelId = String(params.reelId || '')

  const [flow, setFlow] = useState<Flow | null>(null)
  const [reelConfig, setReelConfig] = useState<ReelConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [validationErrors, setValidationErrors] = useState<string[]>([])

  const flowPreview = useMemo(() => {
    if (!flow) return []
    return flow.steps.map((step, index) => buildPreviewItem(step, index))
  }, [flow])

  const loadReelAutomation = async () => {
    if (!reelId) return
    const data = await getReelFull(reelId)
    const config = data.config
    setReelConfig(config)

    const desiredFlowId =
      (config.flow_id || '').trim() || `reel_${reelId.replace(/[^a-zA-Z0-9_]/g, '_')}_flow`

    if (data.flow) {
      setFlow(data.flow)
      return
    }

    const fresh = createEmptyFlow()
    setFlow({
      ...fresh,
      id: desiredFlowId,
      name: `Reel Automation ${reelId.slice(-6)}`,
    })
  }

  useEffect(() => {
    if (!reelId) return
    ;(async () => {
      try {
        await loadReelAutomation()
      } catch (e) {
        console.error(e)
        setError('Failed to load reel automation flow.')
      } finally {
        setLoading(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reelId])

  const updateReelConfig = (patch: Partial<ReelConfig>) => {
    if (!reelConfig) return
    setReelConfig({ ...reelConfig, ...patch })
  }

  const handleSaveAll = async () => {
    if (!flow || !reelConfig) return
    setError('')
    setSuccess('')
    const errors = validateFlow(flow)
    setValidationErrors(errors)
    if (errors.length) return

    const flowId =
      (flow.id || '').trim() || `reel_${reelId.replace(/[^a-zA-Z0-9_]/g, '_')}_flow`
    const flowPayload: Flow = { ...flow, id: flowId }
    const configPayload: ReelConfig = { ...reelConfig, flow_id: flowId }

    setSaving(true)
    try {
      // Run sequentially to avoid race condition in serverless
      const savedFlow = await saveFlow(flowPayload)
      await axios.put(`${API_URL}/api/reels/${reelId}`, configPayload)
      
      setFlow(savedFlow)
      await loadReelAutomation()
      setSuccess('Saved reel settings and flow successfully.')
    } catch (e) {
      console.error(e)
      setError('Failed to save reel automation.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 flex items-center justify-center">
        <div className="text-white text-xl">Loading reel automation...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-white">Reel Automation Flow</h1>
            <p className="text-white/70 mt-1">
              Reel ID: <span className="text-white">{reelId}</span>
            </p>
            <p className="text-white/60 text-sm mt-1">
              Configure keyword, responses, and flow for this reel in one place.
            </p>
          </div>
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-white hover:bg-white/20"
          >
            Back
          </button>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-300/30 bg-rose-500/20 p-3 text-rose-100 mb-4">{error}</div>
        )}
        {success && (
          <div className="rounded-xl border border-emerald-300/30 bg-emerald-500/20 p-3 text-emerald-100 mb-4">
            {success}
          </div>
        )}
        {!!validationErrors.length && (
          <div className="rounded-xl border border-amber-300/30 bg-amber-500/20 p-3 mb-4">
            <h3 className="font-semibold text-amber-100 mb-2">Fix these before saving:</h3>
            <ul className="list-disc list-inside text-sm text-amber-50 space-y-1">
              {validationErrors.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        <section className="glass rounded-2xl border border-white/20 p-5 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4">Reel Settings</h2>
          {reelConfig && (
            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm text-white/80">
                Trigger Keyword
                <input
                  value={reelConfig.trigger_keyword}
                  onChange={(e) => updateReelConfig({ trigger_keyword: e.target.value })}
                  className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                />
              </label>
              <label className="text-sm text-white/80">
                DM Message
                <input
                  value={reelConfig.dm_message}
                  onChange={(e) => updateReelConfig({ dm_message: e.target.value })}
                  className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                />
              </label>
              <label className="text-sm text-white/80 md:col-span-2">
                Comment Reply
                <input
                  value={reelConfig.comment_reply}
                  onChange={(e) => updateReelConfig({ comment_reply: e.target.value })}
                  className="mt-1 w-full rounded-xl bg-white/10 border border-white/20 px-3 py-2 text-white"
                />
              </label>
              <label className="inline-flex items-center gap-2 text-white">
                <input
                  type="checkbox"
                  checked={reelConfig.active}
                  onChange={(e) => updateReelConfig({ active: e.target.checked })}
                  className="h-4 w-4"
                />
                Reel automation active
              </label>
            </div>
          )}
        </section>

        <div className="grid gap-6 lg:grid-cols-[1.8fr_1fr]">
          <main className="glass rounded-2xl border border-white/20 p-5 space-y-4">
            {flow ? <FlowEditor flow={flow} onChange={setFlow} /> : <div className="text-white/70">No flow loaded.</div>}
            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleSaveAll}
                disabled={saving}
                className="rounded-xl bg-gradient-to-r from-pink-500 to-purple-500 px-6 py-3 font-semibold text-white disabled:opacity-60"
              >
                {saving ? 'Saving...' : 'Save All'}
              </button>
            </div>
          </main>

          <aside className="glass rounded-2xl border border-white/20 p-5 h-fit">
            <h3 className="text-lg font-semibold text-white mb-3">Live DM Preview</h3>
            <div className="space-y-3">
              {flowPreview.length === 0 && <p className="text-white/60 text-sm">No steps yet.</p>}
              {flowPreview.map((item) => (
                <div key={item.key} className="rounded-xl border border-white/15 bg-black/20 p-3">
                  <p className="text-xs uppercase tracking-wide text-cyan-200 mb-2">{item.label}</p>
                  <p className="text-sm text-white/90 whitespace-pre-wrap">{item.body}</p>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}

function buildPreviewItem(step: FlowStep, index: number) {
  const key = `${step.id}-${index}`
  const label = `Step ${index + 1}: ${getStepTypeLabel(step.type)}`
  if (step.type === 'text') {
    return { key, label, body: step.message?.trim() || '(empty message)' }
  }
  if (step.type === 'quick_reply') {
    const options = (step.quick_replies || []).map((option) => option.title || '(untitled)').join(' • ')
    return {
      key,
      label,
      body: `${step.message?.trim() || '(empty message)'}\nOptions: ${options || '(none)'}`,
    }
  }
  if (step.type === 'button_template') {
    const buttons = (step.buttons || [])
      .map((button) => `${button.title || '(untitled)'} [${button.type}]`)
      .join(' • ')
    return {
      key,
      label,
      body: `${step.title || '(empty title)'}\n${step.subtitle || ''}\nButtons: ${buttons || '(none)'}`,
    }
  }
  if (step.type === 'condition') {
    return {
      key,
      label,
      body: `Check: follow_confirmed\nTrue -> ${step.condition?.onTrue || '(missing)'}\nFalse -> ${
        step.condition?.onFalse || '(missing)'
      }`,
    }
  }
  return { key, label, body: 'Flow ends here.' }
}
