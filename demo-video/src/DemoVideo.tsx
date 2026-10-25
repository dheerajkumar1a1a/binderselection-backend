import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

const NAVY = '#0f172a';
const ACCENT = '#2563eb';
const WHITE = '#ffffff';

const scenes = [
  { file: 'screenshots/01_01_workboard.png', title: 'Workboard', caption: 'Persistent cases, status chips, SLA clocks, open-round tracking' },
  { file: 'screenshots/02_02_case_new.png', title: 'Case Detail', caption: 'Run evaluation, extracted facts with provenance, per-binder results' },
  { file: 'screenshots/03_03_evaluation.png', title: 'Evaluation Result', caption: 'Recommended binder, capacity snapshot, rule outcomes' },
  { file: 'screenshots/04_05_decision_form.png', title: 'Underwriter Decision', caption: 'Accept / Override / Refer back — a named human always decides' },
  { file: 'screenshots/05_06_decision_recorded.png', title: 'Decision Recorded', caption: 'Append-only decision history, letter link, audit ID' },
  { file: 'screenshots/06_07_round_issued.png', title: 'Request Round Issued', caption: 'Engine-named gaps, 10-business-day SLA, broker notified' },
  { file: 'screenshots/07_08_rules_console.png', title: 'Rules Console', caption: 'Maker-checker proposals, four-eyes approval, effective-dating' },
  { file: 'screenshots/08_09_capacity_desk.png', title: 'Capacity Desk', caption: 'Live ledger, reservations, 80/90% alerts, manual release' },
  { file: 'screenshots/09_10_reference_data.png', title: 'Reference Data', caption: 'Third-party facts with source, licence, timestamp' },
  { file: 'screenshots/10_11_admin_users.png', title: 'Admin & Users', caption: 'Provision accounts, reset passwords, one identity model' },
  { file: 'screenshots/11_12_broker_portal.png', title: 'Broker Portal', caption: 'Restricted view — ask-lists, own docs, outcome letters only' },
];

const INTRO_FRAMES = 90; // 3s
const SCENE_FRAMES = 150; // 5s each
const OUTRO_FRAMES = 90; // 3s

export const DemoVideo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Intro card
  if (frame < INTRO_FRAMES) {
    const opacity = interpolate(frame, [0, 20, INTRO_FRAMES - 20, INTRO_FRAMES], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
    const scale = spring({ frame, fps, config: { damping: 200 } });
    return (
      <AbsoluteFill style={{ background: `linear-gradient(135deg, ${NAVY} 0%, #1e293b 100%)`, justifyContent: 'center', alignItems: 'center', opacity }}>
        <div style={{ textAlign: 'center', transform: `scale(${scale})` }}>
          <h1 style={{ color: WHITE, fontSize: 56, fontWeight: 700, margin: 0, letterSpacing: -1 }}>Binder Selection Agent</h1>
          <p style={{ color: '#94a3b8', fontSize: 24, marginTop: 16 }}>Production System of Record for Marine Cargo Placement</p>
          <p style={{ color: ACCENT, fontSize: 18, marginTop: 32, fontWeight: 600 }}>AI never decides. A named human always does — with full provenance.</p>
        </div>
      </AbsoluteFill>
    );
  }

  // Outro card
  const outroStart = INTRO_FRAMES + scenes.length * SCENE_FRAMES;
  if (frame >= outroStart) {
    const f = frame - outroStart;
    const opacity = interpolate(f, [0, 20, OUTRO_FRAMES - 20, OUTRO_FRAMES], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
    return (
      <AbsoluteFill style={{ background: `linear-gradient(135deg, ${NAVY} 0%, #1e293b 100%)`, justifyContent: 'center', alignItems: 'center', opacity }}>
        <div style={{ textAlign: 'center' }}>
          <h1 style={{ color: WHITE, fontSize: 48, fontWeight: 700, margin: 0 }}>Key Takeaways</h1>
          <ul style={{ color: '#cbd5e1', fontSize: 20, marginTop: 24, textAlign: 'left', lineHeight: 1.8 }}>
            <li>AI never decides — a named human always does</li>
            <li>Missing data becomes a named request, never a silent Pass</li>
            <li>Every fact carries provenance (source + quote or feed + licence)</li>
            <li>Everything append-only — evaluations, decisions, rounds</li>
            <li>Broker portal: restricted view, respond-only</li>
            <li>Maker-checker rulesets with effective-dating</li>
          </ul>
          <p style={{ color: ACCENT, fontSize: 16, marginTop: 32 }}>188 tests green · 6 phases shipped · v1.16.0</p>
        </div>
      </AbsoluteFill>
    );
  }

  // Scene
  const sceneIndex = Math.floor((frame - INTRO_FRAMES) / SCENE_FRAMES);
  const sceneFrame = (frame - INTRO_FRAMES) % SCENE_FRAMES;
  const scene = scenes[Math.min(sceneIndex, scenes.length - 1)];

  const imgOpacity = interpolate(sceneFrame, [0, 15, SCENE_FRAMES - 15, SCENE_FRAMES], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const imgScale = interpolate(sceneFrame, [0, SCENE_FRAMES], [1.0, 1.05], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const titleY = interpolate(sceneFrame, [0, 20], [30, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const titleOpacity = interpolate(sceneFrame, [0, 20, SCENE_FRAMES - 15, SCENE_FRAMES], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: NAVY }}>
      {/* Screenshot with Ken Burns zoom */}
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', opacity: imgOpacity }}>
        <Img
          src={staticFile(scene.file)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'contain',
            transform: `scale(${imgScale})`,
            transformOrigin: 'center center',
          }}
        />
      </div>
      {/* Title bar overlay */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        background: 'linear-gradient(to top, rgba(15,23,42,0.95) 0%, rgba(15,23,42,0.7) 60%, transparent 100%)',
        padding: '40px 48px 32px',
        opacity: titleOpacity,
        transform: `translateY(${titleY}px)`,
      }}>
        <h2 style={{ color: WHITE, fontSize: 32, fontWeight: 700, margin: 0, letterSpacing: -0.5 }}>{scene.title}</h2>
        <p style={{ color: '#94a3b8', fontSize: 16, marginTop: 6, marginBottom: 0 }}>{scene.caption}</p>
      </div>
      {/* Scene counter */}
      <div style={{ position: 'absolute', top: 24, right: 32, color: 'rgba(255,255,255,0.5)', fontSize: 14, fontWeight: 600 }}>
        {sceneIndex + 1} / {scenes.length}
      </div>
    </AbsoluteFill>
  );
};
