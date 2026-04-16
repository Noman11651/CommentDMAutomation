'use client'

import { useEffect, useMemo, useState } from 'react'
import FlowEditor from '@/components/flow-builder/FlowEditor'
import { Flow, createEmptyFlow, listFlows, saveFlow, validateFlow } from '@/lib/flow-api'

export default function FlowsPage() {
  const [flows, setFlows] = useState<Flow[]>([])
  const [selectedFlowId, setSelectedFlowId] = useState<string>('')
  const [editingFlow, setEditingFlow] = useState<Flow | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string>('')
  const [success, setSuccess] = useState<string>('')
  const [validationErrors, setValidationErrors] = useState<string[]>([])

  const selectedFlow = useMemo(
    () => flows.find((flow) => flow.id === selectedFlowId) || null,
    [flows, selectedFlowId]
  )

  const refreshFlows = async () => {
    const nextFlows = await listFlows()
    setFlows(nextFlows)
    if (!nextFlows.length) {
      const empty = createEmptyFlow()
      setEditingFlow(empty)
      setSelectedFlowId('')
      return
    }
    if (!selectedFlowId || !nextFlows.some((flow) => flow.id === selectedFlowId)) {
      setSelectedFlowId(nextFlows[0].id || '')
      setEditingFlow(nextFlows[0])
      return
    }
    const current = nextFlows.find((flow) => flow.id === selectedFlowId) || null
    setEditingFlow(current)
  }

  useEffect(() => {
    ;(async () => {
      try {
        await refreshFlows()
      } catch (e) {
        console.error(e)
        setError('Failed to load flows.')
      } finally {
        setLoading(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSelectFlow = (flow: Flow) => {
    setSelectedFlowId(flow.id || '')
    setEditingFlow(flow)
    setValidationErrors([])
    setError('')
    setSuccess('')
  }

  const handleCreateFlow = () => {
    const fresh = createEmptyFlow()
    setSelectedFlowId('')
    setEditingFlow(fresh)
    setValidationErrors([])
    setError('')
    setSuccess('')
  }

  const handleSave = async () => {
    if (!editingFlow) return
    setError('')
    setSuccess('')
    const errors = validateFlow(editingFlow)
    setValidationErrors(errors)
    if (errors.length) return

    setSaving(true)
    try {
      const saved = await saveFlow(editingFlow)
      setSuccess(`Flow "${saved.name}" saved.`)
      await refreshFlows()
      if (saved.id) {
        setSelectedFlowId(saved.id)
      }
    } catch (e) {
      console.error(e)
      setError('Failed to save flow.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 flex items-center justify-center">
        <div className="text-white text-xl">Loading flow builder...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-white">Flow Builder</h1>
            <p className="text-white/70 mt-1">Create Manychat-style flows with buttons, quick replies, and follow gate.</p>
          </div>
        </div>

        <div className="grid lg:grid-cols-[320px_1fr] gap-6">
          <aside className="glass rounded-2xl border border-white/20 p-4 space-y-4 h-fit">
            <div className="flex items-center justify-between">
              <h2 className="text-white text-lg font-semibold">Saved Flows</h2>
              <button
                type="button"
                onClick={handleCreateFlow}
                className="rounded-lg bg-cyan-500/30 px-3 py-1 text-xs text-cyan-100"
              >
                New
              </button>
            </div>
            <div className="space-y-2">
              {flows.map((flow) => (
                <button
                  key={flow.id}
                  type="button"
                  onClick={() => handleSelectFlow(flow)}
                  className={`w-full rounded-xl border px-3 py-2 text-left ${
                    selectedFlow?.id === flow.id
                      ? 'border-cyan-300 bg-cyan-500/20 text-cyan-50'
                      : 'border-white/10 bg-white/5 text-white/90 hover:bg-white/10'
                  }`}
                >
                  <div className="font-medium truncate">{flow.name}</div>
                  <div className="text-xs opacity-70 truncate">{flow.id}</div>
                </button>
              ))}
              {!flows.length && (
                <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white/70">
                  No saved flows yet.
                </div>
              )}
            </div>
          </aside>

          <main className="glass rounded-2xl border border-white/20 p-5 space-y-4">
            {error && (
              <div className="rounded-xl border border-rose-300/30 bg-rose-500/20 p-3 text-rose-100">{error}</div>
            )}
            {success && (
              <div className="rounded-xl border border-emerald-300/30 bg-emerald-500/20 p-3 text-emerald-100">
                {success}
              </div>
            )}
            {!!validationErrors.length && (
              <div className="rounded-xl border border-amber-300/30 bg-amber-500/20 p-3">
                <h3 className="font-semibold text-amber-100 mb-2">Fix these before saving:</h3>
                <ul className="list-disc list-inside text-sm text-amber-50 space-y-1">
                  {validationErrors.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {editingFlow ? (
              <>
                <FlowEditor flow={editingFlow} onChange={setEditingFlow} />
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving}
                    className="rounded-xl bg-gradient-to-r from-pink-500 to-purple-500 px-6 py-3 font-semibold text-white disabled:opacity-60"
                  >
                    {saving ? 'Saving...' : 'Save Flow'}
                  </button>
                </div>
              </>
            ) : (
              <div className="text-white/70">Select a flow on the left, or create a new one.</div>
            )}
          </main>
        </div>
      </div>
    </div>
  )
}
