/**
 * AudioWorklet processor — Float32 PCM → Int16 PCM 변환 + 16kHz 다운샘플링.
 * AudioContext 기본 샘플레이트(보통 44100/48000)에서 targetSampleRate(16000)으로
 * 단순 데시메이션(소수점 버림). 음성 영역(300~3400Hz)은 16kHz로 충분히 재현된다.
 */
class PcmProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this._targetRate =
      (options &&
        options.processorOptions &&
        options.processorOptions.targetSampleRate) ||
      16000;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel || channel.length === 0) return true;

    // sampleRate: AudioWorkletGlobalScope 전역 — AudioContext 실제 샘플레이트
    const ratio = sampleRate / this._targetRate;
    const outLen = Math.floor(channel.length / ratio);
    if (outLen === 0) return true;

    const int16 = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const srcIdx = Math.min(Math.floor(i * ratio), channel.length - 1);
      const s = Math.max(-1, Math.min(1, channel[srcIdx]));
      // Float32 [-1, 1] → Int16 [-32768, 32767]
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    // Transferable로 전달 — 복사 없이 Main Thread에서 WebSocket.send()
    this.port.postMessage(int16.buffer, [int16.buffer]);
    return true; // 입출력 없어도 프로세서 살려두기
  }
}

registerProcessor("pcm-processor", PcmProcessor);
