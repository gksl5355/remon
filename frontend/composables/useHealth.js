import { ref } from 'vue'
import { checkHealthAPI } from '../services/api.js'

export function useHealth() {
  const status = ref('')
  const refresh = async () => { status.value = (await checkHealthAPI()).status }
  return { status, refresh }
}
