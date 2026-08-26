import { useState } from 'react'

export function useQuery() {
  const [results, setResults] = useState(null)
  return { results, query: async () => {} }
}
