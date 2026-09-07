// useAlarmWatcher.js
// Custom hook I wrote to watch for triggered alarms in the background.
// When a venue the user cares about goes free, we surface an alert.

import { useState, useEffect, useRef, useCallback } from 'react'
import { alarmsApi } from '../api/alarms.js'

const POLL_MS = 10_000

/**
 * Polls /alarms/ every 10s. When an alarm transitions to triggered=true
 * for the first time this session, fires the sound + vibration and surfaces
 * the alarm object so the UI can show an alert.
 */
export function useAlarmWatcher(enabled = true) {
  const [alarms, setAlarms] = useState([])
  const [activeAlert, setActiveAlert] = useState(null)  // the alarm currently ringing
  const knownTriggered = useRef(new Set())              // ids we've already alerted on
  const audioCtx = useRef(null)
  const oscillators = useRef([])
  const vibrateInterval = useRef(null)

  // ── Sound ────────────────────────────────────────────────────────────────

  const startSound = useCallback(() => {
    try {
      if (!audioCtx.current || audioCtx.current.state === 'closed') {
        audioCtx.current = new (window.AudioContext || window.webkitAudioContext)()
      }
      const ctx = audioCtx.current

      const scheduleBeep = (startAt, freq, duration) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)

        osc.type = 'square'
        osc.frequency.setValueAtTime(freq, startAt)
        gain.gain.setValueAtTime(0, startAt)
        gain.gain.linearRampToValueAtTime(0.4, startAt + 0.01)
        gain.gain.setValueAtTime(0.4, startAt + duration - 0.02)
        gain.gain.linearRampToValueAtTime(0, startAt + duration)

        osc.start(startAt)
        osc.stop(startAt + duration)
        oscillators.current.push(osc)
        return osc
      }

      // Two-tone siren pattern repeated every 1.2s
      const playPattern = () => {
        if (!audioCtx.current || audioCtx.current.state === 'closed') return
        const now = audioCtx.current.currentTime
        scheduleBeep(now,        880, 0.4)
        scheduleBeep(now + 0.5,  660, 0.4)
        scheduleBeep(now + 1.0,  880, 0.4)
        scheduleBeep(now + 1.5,  660, 0.4)
      }

      playPattern()
      // Keep repeating — clear oscillators list and schedule more
      const loop = setInterval(() => {
        oscillators.current = []
        playPattern()
      }, 2000)
      oscillators.current.push({ stop: () => clearInterval(loop) })

    } catch (e) {
      console.warn('Web Audio not available:', e)
    }
  }, [])

  const stopSound = useCallback(() => {
    oscillators.current.forEach(o => { try { o.stop() } catch (_) {} })
    oscillators.current = []
    try { audioCtx.current?.close() } catch (_) {}
    audioCtx.current = null
  }, [])

  // ── Vibration ────────────────────────────────────────────────────────────

  const startVibration = useCallback(() => {
    if (!navigator.vibrate) return
    const pattern = [400, 200, 400, 200, 600, 400]
    navigator.vibrate(pattern)
    vibrateInterval.current = setInterval(() => navigator.vibrate(pattern), 2000)
  }, [])

  const stopVibration = useCallback(() => {
    clearInterval(vibrateInterval.current)
    navigator.vibrate?.(0)
  }, [])

  // ── Snooze / dismiss ─────────────────────────────────────────────────────

  const snooze = useCallback(() => {
    stopSound()
    stopVibration()
    setActiveAlert(null)
  }, [stopSound, stopVibration])

  // ── Polling ──────────────────────────────────────────────────────────────

  const poll = useCallback(async () => {
    if (!enabled) return
    try {
      const data = await alarmsApi.list()
      setAlarms(data)

      const newlyTriggered = data.filter(
        a => a.triggered && !knownTriggered.current.has(a.id)
      )

      if (newlyTriggered.length > 0) {
        // Mark all as known so we don't re-alert
        newlyTriggered.forEach(a => knownTriggered.current.add(a.id))
        // Alert on the most recently triggered one
        const latest = newlyTriggered.at(-1)
        setActiveAlert(latest)
        startSound()
        startVibration()
      } else {
        // Keep known set in sync with what's already triggered on first load
        data.filter(a => a.triggered).forEach(a => knownTriggered.current.add(a.id))
      }
    } catch (_) {
      // Not logged in or network error — silent
    }
  }, [enabled, startSound, startVibration])

  useEffect(() => {
    if (!enabled) return
    poll()
    const t = setInterval(poll, POLL_MS)
    return () => {
      clearInterval(t)
      stopSound()
      stopVibration()
    }
  }, [enabled, poll, stopSound, stopVibration])

  return { alarms, setAlarms, activeAlert, snooze }
}
