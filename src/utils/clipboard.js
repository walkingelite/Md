import { Capacitor } from '@capacitor/core'

/**
 * Writes text to the clipboard.
 * Uses @capacitor/clipboard on native iOS/Android (where navigator.clipboard
 * may be restricted), falls back to the Web Clipboard API in the browser.
 */
export async function writeToClipboard(text) {
  if (Capacitor.isNativePlatform()) {
    const { Clipboard } = await import('@capacitor/clipboard')
    await Clipboard.write({ string: text })
  } else if (navigator.clipboard) {
    await navigator.clipboard.writeText(text)
  }
}
