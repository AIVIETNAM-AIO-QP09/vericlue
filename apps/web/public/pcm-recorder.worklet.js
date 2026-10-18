// AudioWorklet thu PCM float mono: gửi từng khối 128 mẫu về luồng chính (src/lib/capture/voiceRecorder.ts).
// Đặt trong public/ để nạp bằng addModule("/pcm-recorder.worklet.js") mà không cần CSP "blob:".
class PcmRecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (channel) this.port.postMessage(channel.slice());
    return true;
  }
}
registerProcessor("pcm-recorder", PcmRecorderProcessor);
