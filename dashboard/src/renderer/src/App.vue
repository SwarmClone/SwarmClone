<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

type RealtimeEvent =
  | { type: 'status'; stage: string; message: string }
  | { type: 'vad.started' }
  | { type: 'vad.ended' }
  | { type: 'asr.partial'; text: string }
  | { type: 'asr.final'; text: string }
  | { type: 'llm.completed'; text: string }
  | { type: 'tts.started'; task_id: string }
  | { type: 'tts.chunk'; audio_base64: string }
  | { type: 'tts.completed' }
  | { type: 'error'; message: string }

const backendBase = 'http://127.0.0.1:17860'
const backendWs = 'ws://127.0.0.1:17860/api/realtime'

const connected = ref(false)
const listening = ref(false)
const backendStatus = ref('未连接')
const vadStatus = ref('待机')
const asrText = ref('')
const llmText = ref('')
const ttsStatus = ref('待机')
const manualText = ref('你好，请介绍一下 SwarmClone。')
const events = ref<string[]>([])

let socket: WebSocket | null = null
let audioContext: AudioContext | null = null
let source: MediaStreamAudioSourceNode | null = null
let processor: ScriptProcessorNode | null = null
let mediaStream: MediaStream | null = null
let ttsChunks: Uint8Array[] = []

const canListen = computed(() => connected.value && !listening.value)

function logEvent(message: string): void {
  events.value.unshift(`${new Date().toLocaleTimeString()} ${message}`)
  events.value = events.value.slice(0, 80)
}

async function checkBackend(): Promise<void> {
  try {
    const response = await fetch(`${backendBase}/health`)
    const data = await response.json()
    connected.value = data.status === 'ok'
    backendStatus.value = data.speech_configured ? '在线，语音配置已加载' : '在线，但缺少语音配置'
    logEvent(`后端状态：${backendStatus.value}`)
  } catch (error) {
    connected.value = false
    backendStatus.value = `连接失败：${String(error)}`
    logEvent(backendStatus.value)
  }
}

async function startListening(): Promise<void> {
  if (!canListen.value) return
  socket = new WebSocket(backendWs)
  socket.binaryType = 'arraybuffer'
  socket.onmessage = (event) => handleRealtimeEvent(JSON.parse(event.data) as RealtimeEvent)
  socket.onerror = () => logEvent('实时 WebSocket 发生错误')
  socket.onclose = () => {
    listening.value = false
    vadStatus.value = '已断开'
    logEvent('实时链路已关闭')
  }

  await new Promise<void>((resolve) => {
    socket!.onopen = () => resolve()
  })

  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
  audioContext = new AudioContext()
  source = audioContext.createMediaStreamSource(mediaStream)
  processor = audioContext.createScriptProcessor(4096, 1, 1)
  processor.onaudioprocess = (event) => {
    if (!socket || socket.readyState !== WebSocket.OPEN || !audioContext) return
    const input = event.inputBuffer.getChannelData(0)
    socket.send(floatToPcm16(resample(input, audioContext.sampleRate, 16000)))
  }
  source.connect(processor)
  processor.connect(audioContext.destination)
  listening.value = true
  vadStatus.value = '监听中'
  logEvent('已开始监听麦克风')
}

function stopListening(): void {
  socket?.send('flush')
  socket?.close()
  processor?.disconnect()
  source?.disconnect()
  mediaStream?.getTracks().forEach((track) => track.stop())
  audioContext?.close()
  socket = null
  processor = null
  source = null
  mediaStream = null
  audioContext = null
  listening.value = false
  vadStatus.value = '已停止'
}

async function runTextFlow(): Promise<void> {
  llmText.value = ''
  ttsStatus.value = '请求中'
  const chat = await fetch(`${backendBase}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role: 'default', text: manualText.value })
  })
  const chatData = await chat.json()
  llmText.value = chatData.text
  logEvent('手动文本已完成 LLM 回复')

  const tts = await fetch(`${backendBase}/api/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: chatData.text })
  })
  const ttsData = await tts.json()
  playAudio([base64ToBytes(ttsData.audio_base64)])
  ttsStatus.value = '已播放'
}

function handleRealtimeEvent(event: RealtimeEvent): void {
  switch (event.type) {
    case 'status':
      logEvent(`${event.stage}: ${event.message}`)
      break
    case 'vad.started':
      vadStatus.value = '检测到说话'
      logEvent('VAD 开始')
      break
    case 'vad.ended':
      vadStatus.value = '语音结束，识别中'
      logEvent('VAD 结束')
      break
    case 'asr.partial':
      asrText.value = event.text
      break
    case 'asr.final':
      asrText.value = event.text
      logEvent(`ASR：${event.text}`)
      break
    case 'llm.completed':
      llmText.value = event.text
      logEvent('LLM 回复完成')
      break
    case 'tts.started':
      ttsChunks = []
      ttsStatus.value = `合成中 ${event.task_id}`
      break
    case 'tts.chunk':
      ttsChunks.push(base64ToBytes(event.audio_base64))
      break
    case 'tts.completed':
      playAudio(ttsChunks)
      ttsStatus.value = '播放中'
      logEvent('TTS 音频已接收')
      break
    case 'error':
      logEvent(`错误：${event.message}`)
      break
  }
}

function resample(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return input
  const ratio = fromRate / toRate
  const length = Math.floor(input.length / ratio)
  const output = new Float32Array(length)
  for (let i = 0; i < length; i += 1) {
    output[i] = input[Math.floor(i * ratio)] ?? 0
  }
  return output
}

function floatToPcm16(input: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(input.length * 2)
  const view = new DataView(buffer)
  input.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample))
    view.setInt16(index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  })
  return buffer
}

function base64ToBytes(base64: string): Uint8Array {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return bytes
}

function playAudio(chunks: Uint8Array[]): void {
  const parts = chunks.map((chunk) => {
    const copy = new Uint8Array(chunk.byteLength)
    copy.set(chunk)
    return copy.buffer
  })
  const blob = new Blob(parts, { type: 'audio/mpeg' })
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  audio.onended = () => URL.revokeObjectURL(url)
  void audio.play()
}

onBeforeUnmount(() => stopListening())
void checkBackend()
</script>

<template>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">SwarmClone 控制台</p>
        <h1>AI 虚拟主播实时链路</h1>
        <p class="subtitle">麦克风音频经过后端 VAD、Fun-ASR、DeepSeek 和 CosyVoice 后回到 Dashboard 播放。</p>
      </div>
      <button @click="checkBackend">刷新后端状态</button>
    </section>

    <section class="grid">
      <article class="card status-card">
        <h2>链路状态</h2>
        <div class="status-row"><span>Backend</span><strong>{{ backendStatus }}</strong></div>
        <div class="status-row"><span>VAD</span><strong>{{ vadStatus }}</strong></div>
        <div class="status-row"><span>TTS</span><strong>{{ ttsStatus }}</strong></div>
        <div class="actions">
          <button :disabled="!canListen" @click="startListening">开始监听</button>
          <button :disabled="!listening" @click="stopListening">停止监听</button>
        </div>
      </article>

      <article class="card conversation">
        <h2>对话结果</h2>
        <label>ASR 识别</label>
        <p class="bubble user">{{ asrText || '等待语音输入...' }}</p>
        <label>LLM 回复</label>
        <p class="bubble assistant">{{ llmText || '等待模型回复...' }}</p>
      </article>

      <article class="card manual">
        <h2>文本烟测</h2>
        <textarea v-model="manualText" />
        <button :disabled="!connected" @click="runTextFlow">运行 LLM -> TTS</button>
      </article>

      <article class="card modules">
        <h2>模块骨架</h2>
        <div>弹幕接入：待实现</div>
        <div>直播平台：待实现</div>
        <div>角色设定：已接入 default role</div>
        <div>音色配置：读取本地 config.toml</div>
      </article>

      <article class="card logs">
        <h2>实时事件</h2>
        <p v-for="event in events" :key="event">{{ event }}</p>
      </article>
    </section>
  </main>
</template>

<style scoped>
:global(body) {
  margin: 0;
  min-height: 100vh;
  background: radial-gradient(circle at top left, #263c72, #0b1020 42%, #070914);
  color: #edf2ff;
  font-family: Inter, "Microsoft YaHei", system-ui, sans-serif;
}

.shell { padding: 36px; }
.hero { display: flex; justify-content: space-between; gap: 24px; align-items: center; margin-bottom: 28px; }
.eyebrow { color: #7dd3fc; letter-spacing: 0.18em; text-transform: uppercase; }
h1 { font-size: 44px; margin: 8px 0; }
h2 { margin-top: 0; }
.subtitle { color: #b8c4e6; max-width: 760px; }
.grid { display: grid; grid-template-columns: 1fr 1.4fr; gap: 18px; }
.card { background: rgba(15, 23, 42, 0.78); border: 1px solid rgba(148, 163, 184, 0.22); border-radius: 24px; padding: 22px; box-shadow: 0 24px 80px rgba(0, 0, 0, 0.3); }
.status-row { display: flex; justify-content: space-between; gap: 18px; padding: 12px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.14); }
.actions { display: flex; gap: 12px; margin-top: 18px; }
button { border: 0; border-radius: 999px; padding: 11px 18px; background: linear-gradient(135deg, #38bdf8, #818cf8); color: #06111f; font-weight: 700; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: 0.45; }
.conversation { grid-row: span 2; }
label { display: block; color: #93c5fd; margin: 14px 0 8px; }
.bubble { min-height: 92px; border-radius: 18px; padding: 16px; line-height: 1.7; }
.user { background: rgba(14, 165, 233, 0.13); }
.assistant { background: rgba(129, 140, 248, 0.16); }
textarea { box-sizing: border-box; width: 100%; min-height: 130px; border-radius: 16px; border: 1px solid rgba(148, 163, 184, 0.3); background: rgba(2, 6, 23, 0.62); color: #edf2ff; padding: 14px; resize: vertical; }
.manual button { margin-top: 12px; }
.modules div { padding: 10px 0; color: #cbd5e1; }
.logs { grid-column: 1 / -1; max-height: 260px; overflow: auto; }
.logs p { margin: 8px 0; color: #cbd5e1; }

@media (max-width: 900px) {
  .shell { padding: 20px; }
  .hero { align-items: flex-start; flex-direction: column; }
  h1 { font-size: 32px; }
  .grid { grid-template-columns: 1fr; }
  .conversation, .logs { grid-column: auto; grid-row: auto; }
}
</style>
