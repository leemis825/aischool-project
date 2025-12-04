// src/services/audioManager.ts
let currentAudio: HTMLAudioElement | null = null;

export function playTtsUrl(url: string) {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
  }
  const audio = new Audio(url);
  currentAudio = audio;
  audio.play().catch((e) => console.error(e));
}

export function stopTts() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
}
