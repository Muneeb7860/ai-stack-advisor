import React from 'react';
import { Composition, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

/**
 * AI Stack Advisor — 45-Second Interactive Product Walkthrough
 * Built with OpenMontage & Remotion (1080p @ 30fps = 1350 frames)
 */
export const AIStackAdvisorDemo = () => {
  return (
    <Composition
      id="AIStackAdvisorWalkthrough"
      component={VideoTimeline}
      durationInFrames={45 * 30} // 45s at 30fps = 1350 frames
      fps={30}
      width={1920}
      height={1080}
    />
  );
};

const VideoTimeline: React.FC = () => {
  return (
    <div style={{ flex: 1, backgroundColor: '#0a0c11', color: '#e8ebf1', fontFamily: 'Inter, sans-serif' }}>
      {/* Scene 1: Problem Hook (0 - 8s / 240 frames) */}
      <Sequence from={0} durationInFrames={240}>
        <ProblemHookScene />
      </Sequence>

      {/* Scene 2: Instant 45-Dimension Signal Detection (8 - 22s / 420 frames) */}
      <Sequence from={240} durationInFrames={420}>
        <SignalDetectionScene />
      </Sequence>

      {/* Scene 3: Constrained AI Refinement & Token Audit (22 - 35s / 390 frames) */}
      <Sequence from={660} durationInFrames={390}>
        <RefinementAuditScene />
      </Sequence>

      {/* Scene 4: 1-Click Export & Call to Action (35 - 45s / 300 frames) */}
      <Sequence from={1050} durationInFrames={300}>
        <ExportAndOutroScene />
      </Sequence>
    </div>
  );
};

// Scene 1: The Problem Hook
const ProblemHookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 20, 220, 240], [0, 1, 1, 0]);
  const scale = spring({ frame, fps: 30, config: { damping: 12 } });

  return (
    <div style={{ opacity, transform: `scale(${scale})`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 80 }}>
      <div style={{ fontSize: 32, color: '#5b8def', fontWeight: 700, letterSpacing: 2, marginBottom: 16 }}>
        THE ARCHITECTURAL BOTTLENECK
      </div>
      <h1 style={{ fontSize: 72, fontWeight: 800, textAlign: 'center', maxWidth: 1200, lineHeight: 1.15 }}>
        Stop Guessing Your Technical &amp; AI Stack.
      </h1>
      <p style={{ fontSize: 28, color: '#828a99', marginTop: 24, maxWidth: 800, textAlign: 'center' }}>
        Paste raw product requirements. Get a verified 45-dimension enterprise blueprint in 3 seconds.
      </p>
    </div>
  );
};

// Scene 2: Live Analysis & Signal Detection
const SignalDetectionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15, 400, 420], [0, 1, 1, 0]);

  const cards = [
    { title: 'Cloud Infrastructure', pick: 'AWS (ECS Fargate + CDK)', conf: 'High', badge: '#34c98a' },
    { title: 'Database Strategy', pick: 'PostgreSQL + Redis Cache', conf: 'High', badge: '#34c98a' },
    { title: 'LLM & Inference', pick: 'Claude 3.5 Sonnet + vLLM Fallback', conf: 'High', badge: '#34c98a' },
    { title: 'RAG Architecture', pick: 'Hybrid Qdrant + BM25 with RRF', conf: 'High', badge: '#34c98a' },
    { title: 'Security & Guardrails', pick: 'SwishOS Telemetry + WAF Token Gating', conf: 'High', badge: '#34c98a' },
    { title: 'Cost Optimization', pick: '$0.0042 / transaction est. spend', conf: 'Audited', badge: '#5b8def' },
  ];

  return (
    <div style={{ opacity, display: 'flex', flexDirection: 'column', height: '100%', padding: '60px 100px' }}>
      <div style={{ fontSize: 24, color: '#5b8def', fontWeight: 600 }}>INSTANT CLIENT-SIDE SYNTHESIS</div>
      <h2 style={{ fontSize: 48, fontWeight: 800, marginTop: 8 }}>45 Architectural Dimensions Grounded in Signal Detection</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginTop: 40 }}>
        {cards.map((c, i) => {
          const cardSpring = spring({ frame: frame - i * 8, fps: 30 });
          return (
            <div
              key={c.title}
              style={{
                transform: `translateY(${interpolate(cardSpring, [0, 1], [40, 0])}px)`,
                opacity: cardSpring,
                backgroundColor: '#12151d',
                border: '1px solid #1f2430',
                borderRadius: 16,
                padding: 32,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 16, color: '#828a99' }}>{c.title}</span>
                <span style={{ fontSize: 12, padding: '4px 10px', borderRadius: 6, backgroundColor: 'rgba(52, 201, 138, 0.1)', color: c.badge, fontWeight: 700 }}>
                  {c.conf}
                </span>
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, marginTop: 16 }}>{c.pick}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// Scene 3: Constrained AI Refinement
const RefinementAuditScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 15, 370, 390], [0, 1, 1, 0]);

  return (
    <div style={{ opacity, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 80 }}>
      <div style={{ fontSize: 22, color: '#7c5bef', fontWeight: 700, letterSpacing: 1.5 }}>
        CONSTRAINED REASONING &amp; REAL AUDITABILITY
      </div>
      <h2 style={{ fontSize: 56, fontWeight: 800, marginTop: 12, textAlign: 'center' }}>
        Optional AI Refinement with Real Token Tracking
      </h2>
      <div style={{ marginTop: 40, width: '100%', maxWidth: 1000, backgroundColor: '#12151d', border: '1px solid #7c5bef', borderRadius: 20, padding: 40 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #1f2430', paddingBottom: 20 }}>
          <span style={{ fontSize: 20, fontWeight: 600 }}>Refinement Pass #1 — Claude 3.5 Sonnet</span>
          <span style={{ fontSize: 16, color: '#34c98a' }}>Tokens: 412 Input / 86 Output ($0.0025)</span>
        </div>
        <p style={{ fontSize: 20, color: '#9aa1ae', marginTop: 24, lineHeight: 1.6 }}>
          "Adjusted database tier from Single-Node RDS to Aurora Serverless v2 due to detected traffic spikes (&gt;10k req/s) while preserving SOC2 boundary constraints."
        </p>
      </div>
    </div>
  );
};

// Scene 4: Export & Call to Action
const ExportAndOutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 20], [0, 1]);
  const scale = spring({ frame, fps: 30 });

  return (
    <div style={{ opacity, transform: `scale(${scale})`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 80 }}>
      <div style={{ fontSize: 32, color: '#5b8def', fontWeight: 800, letterSpacing: 2 }}>
        SHIP WITH CONFIDENCE
      </div>
      <h1 style={{ fontSize: 68, fontWeight: 900, textAlign: 'center', marginTop: 16 }}>
        1-Click Export to Architecture ADRs &amp; Linear Backlog
      </h1>
      <div style={{ marginTop: 48, display: 'flex', gap: 24 }}>
        <div style={{ padding: '18px 36px', backgroundColor: '#5b8def', color: '#fff', fontSize: 22, fontWeight: 700, borderRadius: 12 }}>
          Open AI Stack Advisor
        </div>
        <div style={{ padding: '18px 36px', backgroundColor: '#171b24', border: '1px solid #1f2430', color: '#e8ebf1', fontSize: 22, fontWeight: 700, borderRadius: 12 }}>
          Run in Claude Desktop via FastMCP
        </div>
      </div>
    </div>
  );
};
