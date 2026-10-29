// Âm thanh cảnh báo tạo bằng Web Audio (không cần file mp3).
// Trình duyệt chỉ cho phát âm thanh sau khi người dùng đã bấm vào trang,
// nên phải gọi unlockAlertSound() trong sự kiện click của nút "Bật âm thanh".

let audioCtx = null;

export function unlockAlertSound() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return false;
  if (!audioCtx) audioCtx = new Ctx();
  if (audioCtx.state === "suspended") audioCtx.resume();
  return true;
}

// 3 tiếng "bíp" ngắn
export function playAlertSound() {
  if (!audioCtx) return;
  const start = audioCtx.currentTime + 0.05;
  for (let i = 0; i < 3; i++) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "square";
    osc.frequency.value = 880;
    const t = start + i * 0.3;
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.15, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(t);
    osc.stop(t + 0.2);
  }
}
