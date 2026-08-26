import { useState } from 'react'

export function useValidation() {
  const [metrics, setMetrics] = useState(null)
  return { metrics, run: async () => {} }
}
