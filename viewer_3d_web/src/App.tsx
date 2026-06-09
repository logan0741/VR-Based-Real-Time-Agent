import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import { useWebSocketPose } from './hooks/useWebSocketPose';
import { Scene } from './Scene';
import './App.css';

function App() {
  const wsUrl = 'ws://127.0.0.1:8000/ws/pose';
  const poseData = useWebSocketPose(wsUrl);

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#1a1a2e' }}>
      <div style={{ position: 'absolute', top: 10, left: 10, color: 'white', zIndex: 10 }}>
        <h2>SMPL-X Web Viewer</h2>
        <p>Status: {poseData ? 'Receiving Data' : 'Waiting for connection...'}</p>
        <p>Frame ID: {poseData?.frame_id || '-'}</p>
      </div>

      <Canvas camera={{ position: [0, 1.5, 3], fov: 50 }}>
        <color attach="background" args={['#1a1a2e']} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 5, 5]} intensity={1} />
        <Grid infiniteGrid fadeDistance={20} sectionColor="#4a4a6a" cellColor="#2a2a4a" />
        <OrbitControls target={[0, 1, 0]} />
        
        {/* We will pass the latest pose to the Scene to animate the skeleton */}
        <Scene pose={poseData} />
      </Canvas>
    </div>
  );
}

export default App;
