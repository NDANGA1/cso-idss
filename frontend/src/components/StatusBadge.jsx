// StatusBadge.jsx — green/red/full availability badge

export default function StatusBadge({ state, size = 'md' }) {
  const sizes = { sm: 'px-2 py-0.5 text-xs', md: 'px-3 py-1 text-sm', lg: 'px-4 py-1.5 text-base' }
  const styles = {
    GREEN: { bg: 'bg-emerald-100 text-emerald-800', dot: 'bg-emerald-500', label: 'Available' },
    FULL:  { bg: 'bg-red-100 text-red-800',         dot: 'bg-red-500',     label: 'Full'      },
    RED:   { bg: 'bg-red-100 text-red-800',         dot: 'bg-red-500',     label: 'Booked'    },
  }
  const s = styles[state] ?? styles.RED
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${sizes[size]} ${s.bg}`}>
      <span className={`w-2 h-2 rounded-full ${s.dot} animate-pulse`} />
      {s.label}
    </span>
  )
}
