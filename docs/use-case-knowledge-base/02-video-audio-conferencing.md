# Video / Audio Conferencing

**Status:** implemented — wired into `pickCompute()` via the `videoConferencing` signal.

**Domain:** Real-time video/voice calls, group meetings, webinars, voice channels — Zoom/Google
Meet/Discord-style products. Research date: August 2026.

## Business context

A team building a product with live video or voice calls between two or more participants. The
defining constraint is real-time, low-latency media transport at scale under unreliable, NAT-bound
networks — a fundamentally different infrastructure problem from request/response web traffic or
even generic WebSocket messaging.

## Signals / triggers

`video call`, `video conferencing`, `video chat`, `voice chat`, `voice channel`, `screen share` /
`screen sharing`, `webinar`, `live video`, `virtual meeting`, `group call`, `1-on-1 call`,
`breakout rooms`, `real-time video`, `WebRTC`, `peer-to-peer call`, `audio conferencing`,
`multi-party call`, `meeting room`, `virtual event`, `recording/transcription of calls`.

## Decision points

### A. Media topology — P2P mesh vs. SFU vs. MCU

**P2P Mesh** — every client sends a separate stream to every other client (N×(N-1) connections).
Zero server media cost, lowest latency, but upload bandwidth/CPU scale linearly per client —
practically limited to **3–5 participants**.

**SFU (Selective Forwarding Unit)** — clients upload one stream; the server forwards it (no
re-encoding) to each subscriber, optionally routing different quality layers per receiver. This is
the **dominant 2026 default** for group calls, roughly 5–1000+ participants. Named platforms:
**LiveKit** (Go-based, cloud-native, strong for AI/voice-agent integrations), **mediasoup**
(Node.js control plane + C++ media plane, low-level/flexible), **Janus** (plugin-based, mature,
telephony hybrids), **Jitsi Videobridge** (full open-source meeting platform, easiest full self-host),
**Pion** (Go WebRTC library for custom SFUs). Managed/commercial: **Daily.co, Agora, 100ms**.

**MCU (Multipoint Control Unit)** — server decodes, mixes/composites, and re-encodes a single
combined stream per participant. Highest server CPU cost (transcoding), lowest client bandwidth/CPU
— useful for low-power endpoints or SIP/telephony bridging. Rarely the primary topology alone in
2026; often combined with SFU in hybrid designs.

### B. NAT traversal — STUN/TURN

STUN lets clients discover their public IP/port for direct connectivity; fails behind symmetric
NATs/restrictive firewalls (common, especially enterprise networks). **TURN** (commonly self-hosted
via **coturn**) relays media when direct connection fails, guaranteeing connectivity at the cost of
extra server bandwidth. Production systems deploy geographically distributed TURN clusters as
fallback for both P2P and SFU-uplink connections. This is not optional hardening — a meaningful
share of real users cannot connect without it.

### C. Signaling, recording, and bandwidth adaptation

**Signaling** is not standardized by WebRTC itself — teams build a WebSocket-based server
(Node.js/Go) to exchange SDP offers/answers and ICE candidates plus room/presence state.
**Recording/transcription**: typically a "headless" bot/composited client joins the SFU room,
captures the stream, pipes it to storage (S3) and an ASR pipeline (Whisper, Deepgram, cloud STT)
for transcription/summary — isolate this from the live media-plane nodes to avoid resource
contention.

**Bandwidth adaptation**: **Simulcast** (client encodes 2–3 parallel resolution/bitrate layers, SFU
forwards the layer matching each subscriber's capacity) and **SVC** (Scalable Video Coding — single
encoded stream with embedded spatial/temporal layers, more bandwidth-efficient but more decode
complexity, less universal support), combined with Google Congestion Control (GCC) for real-time
bitrate estimation.

## Anti-patterns

- **Pure P2P mesh beyond ~4–5 participants** — upload bandwidth and CPU explode combinatorially;
  calls degrade or crash clients.
- **No TURN fallback** — assuming STUN/direct connectivity is enough; a meaningful percentage of
  real users behind symmetric NAT or corporate firewalls simply can't connect without a relay.
- **Ignoring bandwidth adaptation** — sending a single fixed-quality stream to all subscribers
  regardless of downlink causes freezing/lag for constrained users instead of graceful degradation.
- **Treating MCU as default** — over-provisioning transcoding servers when an SFU would suffice,
  driving unnecessary compute cost and added latency.
- **Under-provisioning signaling/session-state infrastructure** — treating signaling as an
  afterthought instead of a stateful, horizontally-scaled service with reconnection/renegotiation
  handling.
- **No recording/transcoding isolation** — running recording on the same media-plane nodes serving
  live participants causes resource contention and jitter for live calls.

## Reference implementations

- **Discord** — SFU-based voice architecture on WebRTC, Rust-based media/voice server layer, Elixir
  for signaling/session orchestration; millions of concurrent voice users via distributed voice
  regions.
- **Zoom** — proprietary distributed multimedia routing architecture, globally distributed data
  centers routing media through nearest edge nodes.
- **Google Meet** — WebRTC-based, uses Google's own congestion control (GCC), globally distributed
  infrastructure.
- **Jitsi Meet** — fully open-source reference architecture: Jitsi Videobridge (SFU) + Jicofo
  (conference focus/signaling orchestrator) + Prosody (XMPP signaling).
- **LiveKit / Daily.co / Agora / 100ms** — commercial/managed SFU platforms, common "buy vs. build"
  reference point for startups.

## As implemented in `index.html`

Wired into `pickCompute(s)` via the `videoConferencing` signal (a `videoNote` appended to every
compute branch flagging that the media plane needs its own dedicated SFU tier, sized by concurrent
participants, not request volume) and a dedicated trade-off card ("Media server topology — P2P mesh
vs. SFU vs. MCU") in `pickTradeoffs(s)`.

## Sources

- [Fora Soft — P2P vs MCU vs SFU for Video Conference App](https://www.forasoft.com/blog/article/p2p-vs-mcu-vs-sfu-for-video-conference-app-805)
- [Digital Samba — P2P, SFU and MCU WebRTC Architectures Explained](https://www.digitalsamba.com/blog/p2p-sfu-and-mcu-webrtc-architectures-explained)
- [BlogGeek.me — Best Open Source WebRTC Media Servers (SFU) 2026](https://bloggeek.me/webrtc-tools/media-servers-oss/)
- [Trembit — LiveKit vs Mediasoup vs Janus: Best WebRTC SFU (2026)](https://trembit.com/blog/choosing-the-right-sfu-janus-vs-mediasoup-vs-livekit-for-telemedicine-platforms/)
- [VideoSDK — TURN Server for WebRTC](https://www.videosdk.live/developer-hub/webrtc/turn-server-for-webrtc)
- [Digital Samba — SVC vs Simulcast in WebRTC (2026)](https://www.digitalsamba.com/blog/svc-vs-simulcast-in-webrtc)
- [Discord Engineering Blog — How Discord Handles Two and Half Million Concurrent Voice Users using WebRTC](https://discord.com/blog/how-discord-handles-two-and-half-million-concurrent-voice-users-using-webrtc)
- [Zoom Technical Library — Architected for Reliability](https://library.zoom.com/admin-corner/architecture-and-design/zoom-architected-for-reliability)
- [BlogGeek.me — What is WebRTC P2P mesh and why it can't scale?](https://bloggeek.me/webrtc-p2p-mesh/)
