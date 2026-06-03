const ALG = { name: 'AES-GCM', length: 256 } as const;
const IV_LEN = 12;

const bufferToBase64 = (buffer: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(buffer)));
const base64ToUint8 = (base64: string) => Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));

export const normalizeEmail = (email: string) => email.trim().toLowerCase();

export async function deriveEncryptionKey(email: string, password: string): Promise<string> {
  const encoder = new TextEncoder();
  const salt = encoder.encode(normalizeEmail(email));
  const keyMaterial = await crypto.subtle.importKey('raw', encoder.encode(password), { name: 'PBKDF2' }, false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt, iterations: 120000 },
    keyMaterial,
    ALG,
    true,
    ['encrypt', 'decrypt']
  );
  const rawKey = await crypto.subtle.exportKey('raw', key);
  return bufferToBase64(rawKey);
}

export async function encryptData(plaintext: string, base64Key: string): Promise<string> {
  const keyBytes = base64ToUint8(base64Key);
  const key = await crypto.subtle.importKey('raw', keyBytes, ALG, false, ['encrypt']);
  const iv = crypto.getRandomValues(new Uint8Array(IV_LEN));
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, encoded);
  const result = new Uint8Array(IV_LEN + ciphertext.byteLength);
  result.set(iv);
  result.set(new Uint8Array(ciphertext), IV_LEN);
  return bufferToBase64(result.buffer);
}

export async function decryptData(base64Cipher: string, base64Key: string): Promise<string> {
  const keyBytes = base64ToUint8(base64Key);
  const key = await crypto.subtle.importKey('raw', keyBytes, ALG, false, ['decrypt']);
  const combined = base64ToUint8(base64Cipher);
  const iv = combined.slice(0, IV_LEN);
  const ciphertext = combined.slice(IV_LEN);
  const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext);
  return new TextDecoder().decode(decrypted);
}

export const getSettingsStorageKey = (email: string) => `mindvideo_encrypted_${normalizeEmail(email)}`;

export async function saveEncryptedSettingsToLocalStorage(email: string, password: string, data: unknown) {
  const key = await deriveEncryptionKey(email, password);
  const cipher = await encryptData(JSON.stringify(data), key);
  window.localStorage.setItem(getSettingsStorageKey(email), cipher);
  return cipher;
}

export async function loadEncryptedSettingsFromLocalStorage(email: string, password: string) {
  const cipher = window.localStorage.getItem(getSettingsStorageKey(email));
  if (!cipher) return null;
  const key = await deriveEncryptionKey(email, password);
  const decrypted = await decryptData(cipher, key);
  return JSON.parse(decrypted) as unknown;
}

export async function downloadEncryptedSettingsFile(email: string, cipher: string) {
  const filename = `${normalizeEmail(email)}Keys.json`;
  const blob = new Blob([cipher], { type: 'application/octet-stream' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
