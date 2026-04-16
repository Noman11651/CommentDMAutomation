'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import axios from 'axios'
import FlowEditor from '@/components/flow-builder/FlowEditor'
import { Flow, createEmptyFlow, saveFlow, validateFlow } from '@/lib/flow-api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ReelConfig {
  trigger_keyword: string
  dm_message: string
  comment_reply: string
  active: boolean
  flow_id?: string
}

interface ReelResponse {
  media_id: string
  config: ReelConfig
}

interface ReelListItem {
  id: string
  caption: string
}

export default function ReelAutomationFlowPage() {
  const params = useParams<{ reelId: string }>()
  const router = useRouter()
  const reelId = String(params.reelId || '')

  const [flow, setFlow] = useState<Flow | null>(null)
  const [reelConfig, setReelConfig] = useState<ReelConfig | null>(null)
  const [reelCaption, setReelCaption] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [validationErrors, setValidationErrors] = useState<string[]>([])

  useEffect(() => {
    if (!reelId) return
    ;(async () => {
      try {
        const [reelRes, flowsRes, reelsRes] = await Promise.all([
          axios.get<ReelResponse>(`${API_URL}/api/reels/${reelId}`),
          axios.get<{ flows: Flow[] }>(`${API_URL}/api/flows`),
          axios.get<{ reels: ReelListItem[] }>(`${API_URL}/api/reels`),
        ])

        const config = reelRes.data.config
        setReelConfig(config)
        const selectedReel = reelsRes.data.reels.find((r) => r.id === reelId)
        setReelCaption(selectedReel?.caption || '')

        const desiredFlowId =
          (config.flow_id || '').trim() || `reel_${reelId.replace(/[^a-zA-Z0-9_]/g, '_')}_flow`
        const existing = (flowsRes.data.flows || []).find((f) => f.id === desiredFlowId)
        if (existing) {
          setFlow(existing)
        } else {
          const fresh = createEmptyFlow()
          setFlow({
            ...fresh,
            id: desiredFlowId,
            name: `Reel Automation ${reelId.slice(-6)}`,
          })
        }
      } catch (e) {
        console.error(e)
        setError('Failed to load reel automation flow.')
      } finally {
        setLoading(false)
      }
    })()
  }, [reelId])

  const handleSaveFlow = async () => {
    if (!flow || !reelConfig) return
    setError('')
    setSuccess('')
    const errors = validateFlow(flow)
    setValidationErrors(errors)
    if (errors.length) return

    setSaving(true)
    try {
      const saved = await saveFlow(flow)
      await axios.put(`${API_URL}/api/reels/${reelId}`, {
        ...reelConfig,
        flow_id: saved.id || flow.id || '',
      })
      setFlow(saved)
      setSuccess('Flow saved and linked to this reel automation.')
    } catch (e) {
      console.error(e)
      setError('Failed to save reel flow.')
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
      <div className="max-w-6xl mx-auto">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-white">Reel Automation Flow</h1>
            <p className="text-white/70 mt-1">
              Reel: <span className="text-white">{reelCaption || reelId}</span>
            </p>
            <p className="text-white/60 text-sm mt-1">
              Configure buttons, links, and follow-gate specifically for this reel.
            </p>
          </div>
          <button
            type="button"
            onClick={() => router.push('/')}
            className="rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-white hover:bg-white/20"
          >
            Back to Automation Tab
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

        <main className="glass rounded-2xl border border-white/20 p-5 space-y-4">
          {flow ? (
            <>
              <FlowEditor flow={flow} onChange={setFlow} />
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleSaveFlow}
                  disabled={saving}
                  className="rounded-xl bg-gradient-to-r from-pink-500 to-purple-500 px-6 py-3 font-semibold text-white disabled:opacity-60"
                >
                  {saving ? 'Saving...' : 'Save Reel Flow'}
                </button>
              </div>
            </>
          ) : (
            <div className="text-white/70">No flow loaded.</div>
          )}
        </main>
      </div>
    </div>
  )
}
